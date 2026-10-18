"""Colectivo/organizador: only their events; never venue rows or other events."""

from datetime import date
from uuid import uuid4

import pytest

from app.data.metrics_repository import (
    EventMetricRow,
    MetricsRepository,
    redact_venue_fields,
)
from app.domain.analytics_scope import (
    event_ids_clause,
    keep_allowed_events,
    organizer_scope,
    resolve_scope,
    venue_scope,
)
from app.domain.metric_definitions import (
    V1_METRICS,
    applies_to_actor,
    metric_by_key,
)

ORGANIZER_V1 = frozenset(
    {
        "revenue",
        "average_ticket",
        "tickets_sold",
        "sellthrough_event",
        "sellthrough_tier",
        "sales_velocity",
        "purchase_peak_hours",
        "buyer_mix",
        "event_comparison",
        "market_by_city",
        "market_by_venue_type",
        "market_by_weekday",
        "market_by_price_band",
    }
)

VENUE_ONLY_V1 = frozenset(
    {
        "occupancy",
        "nightly_attendance",
        "sales_by_night_orders",
        "activity_by_weekday",
        "venue_comparison",
        "period_comparison",
        "attendance_by_gender",
    }
)


def test_catalog_marks_organizer_versus_venue_only() -> None:
    for item in V1_METRICS:
        assert item.applies_to
        assert "venue" in item.applies_to
        if item.key in ORGANIZER_V1:
            assert applies_to_actor(item.key, "organizer")
        if item.key in VENUE_ONLY_V1:
            assert not applies_to_actor(item.key, "organizer")
            assert item.applies_to == frozenset({"venue"})
    assert ORGANIZER_V1.isdisjoint(VENUE_ONLY_V1)
    assert metric_by_key("occupancy").applies_to == frozenset({"venue"})
    assert "organizer" in metric_by_key("event_comparison").applies_to


def test_organizer_without_event_ids_is_fail_closed() -> None:
    account = uuid4()
    scope = organizer_scope(account, frozenset())
    assert scope.requires_event_filter
    assert not scope.allows_venue_grain
    assert scope.allows_event(uuid4()) is False
    where: list[str] = ["account_id = :account_id"]
    assert event_ids_clause(where, {}, scope) is False


def test_organizer_event_filter_sql_uses_in_list() -> None:
    own = uuid4()
    other = uuid4()
    scope = organizer_scope(uuid4(), {own})
    where: list[str] = ["account_id = :account_id"]
    params: dict = {}
    assert event_ids_clause(where, params, scope) is True
    assert "event_id IN :event_ids" in where
    assert params["event_ids"] == [own]
    assert other not in params["event_ids"]


def test_keep_allowed_events_drops_foreign_events() -> None:
    own = uuid4()
    other = uuid4()
    scope = organizer_scope(uuid4(), {own})
    own_row = EventMetricRow(
        account_id=uuid4(),
        event_id=own,
        venue_id=uuid4(),
        event_date=date(2026, 8, 1),
        event_capacity=200,
        venue_aforo=400,
        tickets_sold=80,
        tickets_redeemed=70,
        revenue_cents=8_000_000,
        sellthrough_pct=40.0,
        occupancy_pct=17.5,
        average_ticket_cents=100_000,
    )
    other_row = EventMetricRow(
        account_id=own_row.account_id,
        event_id=other,
        venue_id=own_row.venue_id,
        event_date=date(2026, 8, 8),
        event_capacity=200,
        venue_aforo=400,
        tickets_sold=10,
        tickets_redeemed=8,
        revenue_cents=1_000_000,
        sellthrough_pct=5.0,
        occupancy_pct=2.0,
        average_ticket_cents=100_000,
    )
    kept = keep_allowed_events([own_row, other_row], scope)
    assert [row.event_id for row in kept] == [own]


def test_organizer_rows_never_expose_venue_operation() -> None:
    row = EventMetricRow(
        account_id=uuid4(),
        event_id=uuid4(),
        venue_id=uuid4(),
        event_date=date(2026, 8, 1),
        event_capacity=300,
        venue_aforo=800,
        tickets_sold=100,
        tickets_redeemed=90,
        revenue_cents=5_000_000,
        sellthrough_pct=33.3,
        occupancy_pct=11.25,
        average_ticket_cents=50_000,
    )
    redacted = redact_venue_fields(row)
    assert redacted.venue_id is None
    assert redacted.venue_aforo is None
    assert redacted.occupancy_pct is None
    assert redacted.event_id == row.event_id
    assert redacted.revenue_cents == row.revenue_cents
    assert redacted.event_capacity == 300


def test_venue_scope_does_not_filter_events() -> None:
    account = uuid4()
    scope = venue_scope(account)
    assert scope.allows_venue_grain
    assert scope.allows_event(uuid4())
    where = ["account_id = :account_id"]
    params: dict = {}
    assert event_ids_clause(where, params, scope) is True
    assert "event_id" not in "".join(where)


class _FakeSettings:
    uses_seed_facts = True


@pytest.mark.asyncio
async def test_organizer_cannot_read_venue_grain_from_repository() -> None:
    account = uuid4()
    scope = organizer_scope(account, {uuid4()})
    repo = MetricsRepository(session=None, settings=_FakeSettings())  # type: ignore[arg-type]
    summary = await repo.sales_for_period(
        account, date(2026, 8, 1), date(2026, 8, 14), scope=scope
    )
    assert summary.order_or_ticket_count == 0
    assert summary.grain == "blocked_organizer"
    assert await repo.compare_venues(account, date(2026, 8, 1), date(2026, 8, 14), scope=scope) == []
    assert await repo.list_ticket_sales_by_night(
        account, date(2026, 8, 1), date(2026, 8, 14), scope=scope
    ) == []
    assert await repo.weekday_activity_from_facts(
        account, date(2026, 8, 1), date(2026, 8, 14), scope=scope
    ) == []
    assert await repo.list_weekday_activity(account, scope=scope) == []
    assert await repo.list_buyer_mix_by_month(account, scope=scope) == []


def test_resolve_scope_rejects_account_mismatch() -> None:
    own = uuid4()
    other = uuid4()
    event = uuid4()
    sneaky = organizer_scope(other, {event})
    resolved = resolve_scope(own, sneaky)
    assert resolved.account_id == own
    assert resolved.event_ids == frozenset()
    assert resolved.allows_event(event) is False
