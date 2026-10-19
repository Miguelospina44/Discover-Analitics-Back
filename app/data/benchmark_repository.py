from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.metric_definitions import (
    MIN_MARKET_ACCOUNTS,
    MIN_MARKET_COHORT,
    MIN_MARKET_VENUES,
    normalize_city,
    suppress_market_cell,
)

MarketDimension = Literal["city", "venue_type", "weekday", "price_band"]

SEED_BENCH_SQL = text(
    """
    SELECT
      (SELECT AVG(redeemed_tickets)::float
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_tickets_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY redeemed_tickets)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_tickets_per_venue_night,
      (SELECT AVG(order_count)::float
         FROM analytics.fact_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_orders_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)
         FROM analytics.fact_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_orders_per_venue_night,
      (SELECT COUNT(DISTINCT account_id)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS accounts_in_sample,
      (SELECT COUNT(*)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS nights_in_sample,
      (SELECT COUNT(DISTINCT venue_id)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS venues_in_sample,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'woman'
      ) AS sum_woman,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'man'
      ) AS sum_man,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'other'
      ) AS sum_other,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'undisclosed'
      ) AS sum_undisclosed,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS sum_gender_total
    """
)

DISCOVER_BENCH_SQL = text(
    """
    SELECT
      (SELECT AVG(redeemed_tickets)::float
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_tickets_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY redeemed_tickets)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_tickets_per_venue_night,
      (SELECT AVG(order_count)::float
         FROM analytics.v_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_orders_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)
         FROM analytics.v_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_orders_per_venue_night,
      (SELECT COUNT(DISTINCT account_id)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS accounts_in_sample,
      (SELECT COUNT(*)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS nights_in_sample,
      (SELECT COUNT(DISTINCT venue_id)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS venues_in_sample,
      NULL::float AS sum_woman,
      NULL::float AS sum_man,
      NULL::float AS sum_other,
      NULL::float AS sum_undisclosed,
      NULL::float AS sum_gender_total
    """
)


@dataclass(frozen=True)
class MarketSlice:
    dimension: MarketDimension
    slice_key: str
    venues_in_sample: int
    accounts_in_sample: int
    avg_tickets_per_venue: float | None
    median_tickets_per_venue: float | None
    avg_revenue_cents_per_venue: float | None
    median_avg_ticket_cents: float | None


@dataclass(frozen=True)
class GremialBenchmarks:
    avg_tickets_per_venue_night: float | None
    median_tickets_per_venue_night: float | None
    avg_orders_per_venue_night: float | None
    median_orders_per_venue_night: float | None
    accounts_in_sample: int
    nights_in_sample: int
    share_woman: float | None
    share_man: float | None
    share_other: float | None
    share_undisclosed: float | None


class BenchmarkRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def gremial(
        self,
        period_start: date,
        period_end: date,
    ) -> GremialBenchmarks:
        sql = SEED_BENCH_SQL if self._settings.uses_seed_facts else DISCOVER_BENCH_SQL
        result = await self._session.execute(
            sql,
            {"period_start": period_start, "period_end": period_end},
        )
        row = result.mappings().one()
        venues = int(row["venues_in_sample"] or 0)
        accounts = int(row["accounts_in_sample"] or 0)
        nights = int(row["nights_in_sample"] or 0)
        if suppress_market_cell(venues=venues, accounts=accounts, cohort=nights):
            return _hidden_gremial()

        total = _f(row["sum_gender_total"]) or 0.0

        def share(key: str) -> float | None:
            part = _f(row[key])
            if part is None or total <= 0:
                return None
            return part / total

        return GremialBenchmarks(
            avg_tickets_per_venue_night=_f(row["avg_tickets_per_venue_night"]),
            median_tickets_per_venue_night=_f(row["median_tickets_per_venue_night"]),
            avg_orders_per_venue_night=_f(row["avg_orders_per_venue_night"]),
            median_orders_per_venue_night=_f(row["median_orders_per_venue_night"]),
            accounts_in_sample=accounts,
            nights_in_sample=nights,
            share_woman=share("sum_woman"),
            share_man=share("sum_man"),
            share_other=share("sum_other"),
            share_undisclosed=share("sum_undisclosed"),
        )

    async def list_market_slices(
        self,
        dimension: MarketDimension,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> list[MarketSlice]:
        """Anonymous market trends. Empty when every cell is below the floor."""
        if self._settings.uses_seed_facts:
            return await self._seed_market_slices(dimension, period_start, period_end)
        view = {
            "city": "analytics.v_market_by_city",
            "venue_type": "analytics.v_market_by_venue_type",
            "weekday": "analytics.v_market_by_weekday",
            "price_band": "analytics.v_market_by_price_band",
        }[dimension]
        key_col = {
            "city": "city_normalized",
            "venue_type": "venue_type_normalized",
            "weekday": "iso_weekday",
            "price_band": "price_band",
        }[dimension]
        sql = text(
            f"""
            SELECT {key_col} AS slice_key, venues_in_sample, accounts_in_sample,
                   avg_tickets_per_venue, median_tickets_per_venue,
                   avg_revenue_cents_per_venue, median_avg_ticket_cents
            FROM {view}
            """
        )
        result = await self._session.execute(sql)
        rows: list[MarketSlice] = []
        for row in result.mappings().all():
            slice_row = _slice_from_row(dimension, row)
            if slice_row is not None:
                rows.append(slice_row)
        return rows

    async def _seed_market_slices(
        self,
        dimension: MarketDimension,
        period_start: date | None,
        period_end: date | None,
    ) -> list[MarketSlice]:
        if dimension in {"venue_type", "price_band"}:
            return []
        where = []
        params: dict = {}
        if period_start is not None:
            where.append("f.night_date >= :period_start")
            params["period_start"] = period_start
        if period_end is not None:
            where.append("f.night_date <= :period_end")
            params["period_end"] = period_end
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        if dimension == "city":
            group_expr = "d.city"
        else:
            group_expr = "EXTRACT(ISODOW FROM f.night_date)::int"
        sql = text(
            f"""
            WITH per_venue AS (
                SELECT
                    {group_expr} AS slice_key,
                    f.account_id,
                    f.venue_id,
                    SUM(f.order_count)::int AS tickets_sold,
                    SUM(f.revenue_cents)::bigint AS revenue_cents
                FROM analytics.fact_sales_by_night f
                JOIN analytics.dim_venues d ON d.venue_id = f.venue_id
                {where_sql}
                GROUP BY 1, f.account_id, f.venue_id
            )
            SELECT
                slice_key,
                COUNT(DISTINCT venue_id)::int AS venues_in_sample,
                COUNT(DISTINCT account_id)::int AS accounts_in_sample,
                AVG(tickets_sold)::float AS avg_tickets_per_venue,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tickets_sold)
                    AS median_tickets_per_venue,
                AVG(revenue_cents)::float AS avg_revenue_cents_per_venue,
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY
                        CASE WHEN tickets_sold > 0
                             THEN revenue_cents / tickets_sold END
                ) AS median_avg_ticket_cents,
                SUM(tickets_sold)::int AS cohort
            FROM per_venue
            GROUP BY slice_key
            HAVING COUNT(DISTINCT venue_id) >= {MIN_MARKET_VENUES}
               AND COUNT(DISTINCT account_id) >= {MIN_MARKET_ACCOUNTS}
               AND SUM(tickets_sold) >= {MIN_MARKET_COHORT}
            """
        )
        result = await self._session.execute(sql, params)
        rows: list[MarketSlice] = []
        for row in result.mappings().all():
            key = row["slice_key"]
            if dimension == "city":
                key = normalize_city(str(key) if key is not None else None)
                if key is None:
                    continue
            mapped = {
                "slice_key": key,
                "venues_in_sample": row["venues_in_sample"],
                "accounts_in_sample": row["accounts_in_sample"],
                "avg_tickets_per_venue": row["avg_tickets_per_venue"],
                "median_tickets_per_venue": row["median_tickets_per_venue"],
                "avg_revenue_cents_per_venue": row["avg_revenue_cents_per_venue"],
                "median_avg_ticket_cents": row["median_avg_ticket_cents"],
            }
            slice_row = _slice_from_row(dimension, mapped)
            if slice_row is not None:
                rows.append(slice_row)
        return rows


def _f(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _hidden_gremial() -> GremialBenchmarks:
    """Fail-closed payload: no averages and no small-n leak."""
    return GremialBenchmarks(
        avg_tickets_per_venue_night=None,
        median_tickets_per_venue_night=None,
        avg_orders_per_venue_night=None,
        median_orders_per_venue_night=None,
        accounts_in_sample=0,
        nights_in_sample=0,
        share_woman=None,
        share_man=None,
        share_other=None,
        share_undisclosed=None,
    )


def _slice_from_row(dimension: MarketDimension, row: object) -> MarketSlice | None:
    mapping = row if isinstance(row, dict) else dict(row)  # type: ignore[arg-type]
    venues = int(mapping["venues_in_sample"] or 0)
    accounts = int(mapping["accounts_in_sample"] or 0)
    raw_cohort = mapping.get("cohort")
    cohort = int(raw_cohort) if raw_cohort is not None else MIN_MARKET_COHORT
    if suppress_market_cell(venues=venues, accounts=accounts, cohort=cohort):
        return None
    key = mapping["slice_key"]
    if key is None:
        return None
    return MarketSlice(
        dimension=dimension,
        slice_key=str(key),
        venues_in_sample=venues,
        accounts_in_sample=accounts,
        avg_tickets_per_venue=_f(mapping["avg_tickets_per_venue"]),
        median_tickets_per_venue=_f(mapping["median_tickets_per_venue"]),
        avg_revenue_cents_per_venue=_f(mapping["avg_revenue_cents_per_venue"]),
        median_avg_ticket_cents=_f(mapping["median_avg_ticket_cents"]),
    )
