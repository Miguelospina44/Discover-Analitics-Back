"""Read models for v1 Discover metrics.

Seed path uses existing nightly facts (no Discover tables).
Discover path reads analytics.v_* views — always filtered by account_id.
Never returns buyer-level rows; cohort views already enforce MIN_COHORT_SIZE.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.data.sales_repository import SalesPoint, SalesRepository
from app.domain.analytics_scope import (
    AnalyticsScope,
    event_ids_clause,
    keep_allowed_events,
    resolve_scope,
)
from app.domain.metric_definitions import (
    MIN_COHORT_SIZE,
    average_ticket_cents,
    buyer_mix,
    period_change_pct,
)


@dataclass(frozen=True)
class SalesSummary:
    order_or_ticket_count: int
    revenue_cents: int
    average_ticket_cents: int | None
    grain: str


@dataclass(frozen=True)
class VenueSalesSummary:
    venue_id: UUID
    order_or_ticket_count: int
    revenue_cents: int
    average_ticket_cents: int | None
    account_id: UUID | None = None


@dataclass(frozen=True)
class WeekdaySales:
    iso_weekday: int
    tickets_or_orders: int
    revenue_cents: int


@dataclass(frozen=True)
class PeriodComparison:
    current: SalesSummary
    previous: SalesSummary
    revenue_change_pct: float | None
    volume_change_pct: float | None


@dataclass(frozen=True)
class TicketNightPoint:
    account_id: UUID
    venue_id: UUID
    night_date: date
    tickets_sold: int
    revenue_cents: int


@dataclass(frozen=True)
class EventMetricRow:
    account_id: UUID
    event_id: UUID
    venue_id: UUID | None
    event_date: date
    event_capacity: int | None
    venue_aforo: int | None
    tickets_sold: int
    tickets_redeemed: int
    revenue_cents: int
    sellthrough_pct: float | None
    occupancy_pct: float | None
    average_ticket_cents: int | None


@dataclass(frozen=True)
class TierSellthrough:
    account_id: UUID
    event_id: UUID
    venue_id: UUID | None
    tier_id: UUID
    tier_price_cop: int | None
    tier_capacity: int | None
    tickets_sold: int
    sellthrough_pct: float | None


@dataclass(frozen=True)
class VelocityBucket:
    account_id: UUID
    event_id: UUID
    venue_id: UUID | None
    event_date: date
    window_key: str
    tickets_sold: int
    revenue_cents: int


@dataclass(frozen=True)
class PurchaseHour:
    account_id: UUID
    hour_of_day: int
    tickets_sold: int
    revenue_cents: int


@dataclass(frozen=True)
class BuyerMixRow:
    account_id: UUID
    buyer_count: int
    new_buyers: int
    returning_buyers: int
    new_buyer_pct: float
    event_id: UUID | None = None
    venue_id: UUID | None = None
    order_month: date | None = None


def summarize_sales(points: list[SalesPoint], *, grain: str) -> SalesSummary:
    volume = sum(point.order_count for point in points)
    revenue = sum(point.revenue_cents for point in points)
    return SalesSummary(
        order_or_ticket_count=volume,
        revenue_cents=revenue,
        average_ticket_cents=average_ticket_cents(revenue, volume),
        grain=grain,
    )


def compare_summaries(current: SalesSummary, previous: SalesSummary) -> PeriodComparison:
    return PeriodComparison(
        current=current,
        previous=previous,
        revenue_change_pct=period_change_pct(current.revenue_cents, previous.revenue_cents),
        volume_change_pct=period_change_pct(
            current.order_or_ticket_count,
            previous.order_or_ticket_count,
        ),
    )


def group_sales_by_venue(points: list[SalesPoint]) -> list[VenueSalesSummary]:
    buckets: dict[UUID, list[SalesPoint]] = defaultdict(list)
    for point in points:
        buckets[point.venue_id].append(point)
    rows: list[VenueSalesSummary] = []
    for venue_id, group in buckets.items():
        summary = summarize_sales(group, grain="venue")
        account_id = group[0].account_id
        rows.append(
            VenueSalesSummary(
                venue_id=venue_id,
                order_or_ticket_count=summary.order_or_ticket_count,
                revenue_cents=summary.revenue_cents,
                average_ticket_cents=summary.average_ticket_cents,
                account_id=account_id,
            )
        )
    rows.sort(key=lambda row: row.revenue_cents, reverse=True)
    return rows


def group_sales_by_iso_weekday(points: list[SalesPoint]) -> list[WeekdaySales]:
    volume: dict[int, int] = defaultdict(int)
    revenue: dict[int, int] = defaultdict(int)
    for point in points:
        iso = point.night_date.isoweekday()
        volume[iso] += point.order_count
        revenue[iso] += point.revenue_cents
    return [
        WeekdaySales(
            iso_weekday=day,
            tickets_or_orders=volume[day],
            revenue_cents=revenue[day],
        )
        for day in range(1, 8)
        if day in volume
    ]


def _privacy_mix(
    account_id: UUID,
    new_buyers: int,
    returning_buyers: int,
    *,
    event_id: UUID | None = None,
    venue_id: UUID | None = None,
    order_month: date | None = None,
) -> BuyerMixRow | None:
    mix = buyer_mix(new_buyers, returning_buyers)
    if mix is None:
        return None
    new_count, returning_count, new_pct = mix
    return BuyerMixRow(
        account_id=account_id,
        buyer_count=new_count + returning_count,
        new_buyers=new_count,
        returning_buyers=returning_count,
        new_buyer_pct=new_pct,
        event_id=event_id,
        venue_id=venue_id,
        order_month=order_month,
    )


def redact_venue_fields(row: EventMetricRow) -> EventMetricRow:
    """Organizers never see host-venue operation (aforo, occupancy, venue_id)."""
    return EventMetricRow(
        account_id=row.account_id,
        event_id=row.event_id,
        venue_id=None,
        event_date=row.event_date,
        event_capacity=row.event_capacity,
        venue_aforo=None,
        tickets_sold=row.tickets_sold,
        tickets_redeemed=row.tickets_redeemed,
        revenue_cents=row.revenue_cents,
        sellthrough_pct=row.sellthrough_pct,
        occupancy_pct=None,
        average_ticket_cents=row.average_ticket_cents,
    )


def _bind_events(sql: object, scope: AnalyticsScope) -> object:
    if scope.requires_event_filter and scope.event_ids:
        return sql.bindparams(bindparam("event_ids", expanding=True))
    return sql


class MetricsRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._sales = SalesRepository(session, self._settings)

    async def sales_for_period(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
        venue_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> SalesSummary:
        resolved = resolve_scope(account_id, scope)
        if not resolved.allows_venue_grain:
            return SalesSummary(0, 0, None, grain="blocked_organizer")
        points = await self._sales.list_for_scope(
            account_id,
            period_start,
            period_end,
            venue_id=venue_id,
        )
        grain = "venue_period" if venue_id is not None else "period"
        return summarize_sales(points, grain=grain)

    async def compare_periods(
        self,
        account_id: UUID,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        venue_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> PeriodComparison:
        current = await self.sales_for_period(
            account_id, current_start, current_end, venue_id=venue_id, scope=scope
        )
        previous = await self.sales_for_period(
            account_id, previous_start, previous_end, venue_id=venue_id, scope=scope
        )
        return compare_summaries(current, previous)

    async def compare_venues(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
        scope: AnalyticsScope | None = None,
    ) -> list[VenueSalesSummary]:
        if not resolve_scope(account_id, scope).allows_venue_grain:
            return []
        points = await self._sales.list_for_scope(account_id, period_start, period_end)
        return group_sales_by_venue(points)

    async def weekday_activity_from_facts(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
        scope: AnalyticsScope | None = None,
    ) -> list[WeekdaySales]:
        """Seed-safe weekday mix from nightly sales facts/views."""
        if not resolve_scope(account_id, scope).allows_venue_grain:
            return []
        points = await self._sales.list_for_scope(account_id, period_start, period_end)
        return group_sales_by_iso_weekday(points)

    async def list_ticket_sales_by_night(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
        venue_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[TicketNightPoint]:
        if not resolve_scope(account_id, scope).allows_venue_grain:
            return []
        if self._settings.uses_seed_facts:
            return []
        where = [
            "account_id = :account_id",
            "night_date >= :period_start",
            "night_date <= :period_end",
        ]
        params: dict = {
            "account_id": account_id,
            "period_start": period_start,
            "period_end": period_end,
        }
        if venue_id is not None:
            where.append("venue_id = :venue_id")
            params["venue_id"] = venue_id
        sql = text(
            f"""
            SELECT account_id, venue_id, night_date, tickets_sold, revenue_cents
            FROM analytics.v_ticket_sales_by_night
            WHERE {" AND ".join(where)}
            ORDER BY night_date ASC
            """
        )
        result = await self._session.execute(sql, params)
        return [
            TicketNightPoint(
                account_id=row["account_id"],
                venue_id=row["venue_id"],
                night_date=row["night_date"],
                tickets_sold=int(row["tickets_sold"]),
                revenue_cents=int(row["revenue_cents"]),
            )
            for row in result.mappings().all()
        ]

    async def list_event_metrics(
        self,
        account_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
        event_id: UUID | None = None,
        venue_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[EventMetricRow]:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if period_start is not None:
            where.append("event_date >= :period_start")
            params["period_start"] = period_start
        if period_end is not None:
            where.append("event_date <= :period_end")
            params["period_end"] = period_end
        if event_id is not None:
            if not resolved.allows_event(event_id):
                return []
            where.append("event_id = :event_id")
            params["event_id"] = event_id
        elif not event_ids_clause(where, params, resolved):
            return []
        if venue_id is not None:
            if not resolved.allows_venue_grain:
                return []
            where.append("venue_id = :venue_id")
            params["venue_id"] = venue_id
        sql = text(
            f"""
            SELECT account_id, event_id, venue_id, event_date, event_capacity,
                   venue_aforo, tickets_sold, tickets_redeemed, revenue_cents,
                   sellthrough_pct, occupancy_pct
            FROM analytics.v_event_metrics
            WHERE {" AND ".join(where)}
            ORDER BY event_date DESC, revenue_cents DESC
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        rows: list[EventMetricRow] = []
        for row in result.mappings().all():
            sold = int(row["tickets_sold"])
            revenue = int(row["revenue_cents"] or 0)
            item = EventMetricRow(
                account_id=row["account_id"],
                event_id=row["event_id"],
                venue_id=row["venue_id"],
                event_date=row["event_date"],
                event_capacity=row["event_capacity"],
                venue_aforo=row["venue_aforo"],
                tickets_sold=sold,
                tickets_redeemed=int(row["tickets_redeemed"]),
                revenue_cents=revenue,
                sellthrough_pct=_opt_float(row["sellthrough_pct"]),
                occupancy_pct=_opt_float(row["occupancy_pct"]),
                average_ticket_cents=average_ticket_cents(revenue, sold),
            )
            if resolved.requires_event_filter:
                item = redact_venue_fields(item)
            rows.append(item)
        return keep_allowed_events(rows, resolved)

    async def list_sellthrough_by_tier(
        self,
        account_id: UUID,
        event_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[TierSellthrough]:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if event_id is not None:
            if not resolved.allows_event(event_id):
                return []
            where.append("event_id = :event_id")
            params["event_id"] = event_id
        elif not event_ids_clause(where, params, resolved):
            return []
        sql = text(
            f"""
            SELECT account_id, event_id, venue_id, tier_id, tier_price_cop,
                   tier_capacity, tickets_sold, sellthrough_pct
            FROM analytics.v_sellthrough_by_tier
            WHERE {" AND ".join(where)}
            ORDER BY sellthrough_pct DESC NULLS LAST
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        return keep_allowed_events(
            [
            TierSellthrough(
                account_id=row["account_id"],
                event_id=row["event_id"],
                venue_id=None if resolved.requires_event_filter else row["venue_id"],
                tier_id=row["tier_id"],
                tier_price_cop=_opt_int(row["tier_price_cop"]),
                tier_capacity=_opt_int(row["tier_capacity"]),
                tickets_sold=int(row["tickets_sold"]),
                sellthrough_pct=_opt_float(row["sellthrough_pct"]),
            )
            for row in result.mappings().all()
        ]
        )

    async def list_sales_velocity(
        self,
        account_id: UUID,
        event_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[VelocityBucket]:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if event_id is not None:
            if not resolved.allows_event(event_id):
                return []
            where.append("event_id = :event_id")
            params["event_id"] = event_id
        elif not event_ids_clause(where, params, resolved):
            return []
        sql = text(
            f"""
            SELECT account_id, event_id, venue_id, event_date, window_key,
                   tickets_sold, revenue_cents
            FROM analytics.v_sales_velocity
            WHERE {" AND ".join(where)}
            ORDER BY event_date DESC, window_key
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        return keep_allowed_events(
            [
            VelocityBucket(
                account_id=row["account_id"],
                event_id=row["event_id"],
                venue_id=None if resolved.requires_event_filter else row["venue_id"],
                event_date=row["event_date"],
                window_key=str(row["window_key"]),
                tickets_sold=int(row["tickets_sold"]),
                revenue_cents=int(row["revenue_cents"]),
            )
            for row in result.mappings().all()
        ]
        )

    async def list_purchase_hours(
        self,
        account_id: UUID,
        scope: AnalyticsScope | None = None,
    ) -> list[PurchaseHour]:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if not event_ids_clause(where, params, resolved):
            return []
        sql = text(
            f"""
            SELECT account_id, event_id, hour_of_day, tickets_sold, revenue_cents
            FROM analytics.v_purchase_hours
            WHERE {" AND ".join(where)}
            ORDER BY hour_of_day ASC
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        buckets: dict[int, PurchaseHour] = {}
        for row in result.mappings().all():
            event_id = row["event_id"]
            if not resolved.allows_event(event_id):
                continue
            hour = int(row["hour_of_day"])
            sold = int(row["tickets_sold"])
            revenue = int(row["revenue_cents"])
            prev = buckets.get(hour)
            if prev is None:
                buckets[hour] = PurchaseHour(
                    account_id=row["account_id"],
                    hour_of_day=hour,
                    tickets_sold=sold,
                    revenue_cents=revenue,
                )
            else:
                buckets[hour] = PurchaseHour(
                    account_id=prev.account_id,
                    hour_of_day=hour,
                    tickets_sold=prev.tickets_sold + sold,
                    revenue_cents=prev.revenue_cents + revenue,
                )
        return [buckets[hour] for hour in sorted(buckets)]

    async def list_weekday_activity(
        self,
        account_id: UUID,
        scope: AnalyticsScope | None = None,
    ) -> list[WeekdaySales]:
        if not resolve_scope(account_id, scope).allows_venue_grain:
            return []
        if self._settings.uses_seed_facts:
            return []
        sql = text(
            """
            SELECT iso_weekday, tickets_sold, revenue_cents
            FROM analytics.v_activity_by_weekday
            WHERE account_id = :account_id
            ORDER BY iso_weekday ASC
            """
        )
        result = await self._session.execute(sql, {"account_id": account_id})
        return [
            WeekdaySales(
                iso_weekday=int(row["iso_weekday"]),
                tickets_or_orders=int(row["tickets_sold"]),
                revenue_cents=int(row["revenue_cents"]),
            )
            for row in result.mappings().all()
        ]

    async def list_buyer_mix_by_event(
        self,
        account_id: UUID,
        event_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[BuyerMixRow]:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if event_id is not None:
            if not resolved.allows_event(event_id):
                return []
            where.append("event_id = :event_id")
            params["event_id"] = event_id
        elif not event_ids_clause(where, params, resolved):
            return []
        sql = text(
            f"""
            SELECT account_id, event_id, venue_id, buyer_count, new_buyers, returning_buyers
            FROM analytics.v_buyer_mix_by_event
            WHERE {" AND ".join(where)}
            ORDER BY buyer_count DESC
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        rows: list[BuyerMixRow] = []
        for row in result.mappings().all():
            mix = _privacy_mix(
                row["account_id"],
                int(row["new_buyers"]),
                int(row["returning_buyers"]),
                event_id=row["event_id"],
                venue_id=None if resolved.requires_event_filter else row["venue_id"],
            )
            if mix is not None:
                rows.append(mix)
        return keep_allowed_events(rows, resolved)

    async def list_buyer_mix_by_month(
        self,
        account_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
        scope: AnalyticsScope | None = None,
    ) -> list[BuyerMixRow]:
        if not resolve_scope(account_id, scope).allows_venue_grain:
            return []
        if self._settings.uses_seed_facts:
            return []
        where = ["account_id = :account_id"]
        params: dict = {"account_id": account_id}
        if period_start is not None:
            where.append("order_month >= :period_start")
            params["period_start"] = period_start
        if period_end is not None:
            where.append("order_month <= :period_end")
            params["period_end"] = period_end
        sql = text(
            f"""
            SELECT account_id, order_month, buyer_count, new_buyers, returning_buyers
            FROM analytics.v_buyer_mix_by_month
            WHERE {" AND ".join(where)}
            ORDER BY order_month DESC
            """
        )
        result = await self._session.execute(sql, params)
        rows: list[BuyerMixRow] = []
        for row in result.mappings().all():
            mix = _privacy_mix(
                row["account_id"],
                int(row["new_buyers"]),
                int(row["returning_buyers"]),
                order_month=row["order_month"],
            )
            if mix is not None:
                rows.append(mix)
        return rows


def _opt_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _opt_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


# Re-export so tests and callers can assert the same floor the SQL uses.
COHORT_FLOOR = MIN_COHORT_SIZE
