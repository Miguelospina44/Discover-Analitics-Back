"""Unit tests for metric repository helpers (no database)."""

from datetime import date
from uuid import uuid4

from app.data.metrics_repository import (
    COHORT_FLOOR,
    EventMetricRow,
    _privacy_mix,
    compare_summaries,
    summarize_sales,
)
from app.data.sales_repository import SalesPoint
from app.domain.metric_definitions import MIN_COHORT_SIZE, average_ticket_cents


def test_cohort_floor_matches_domain() -> None:
    assert COHORT_FLOOR == MIN_COHORT_SIZE == 10


def test_privacy_mix_drops_small_cohorts() -> None:
    account = uuid4()
    assert _privacy_mix(account, 4, 5) is None
    row = _privacy_mix(account, 4, 6, event_id=uuid4())
    assert row is not None
    assert row.buyer_count == 10
    assert row.new_buyer_pct == 40.0
    assert row.order_month is None


def test_event_metric_row_average_ticket() -> None:
    row = EventMetricRow(
        account_id=uuid4(),
        event_id=uuid4(),
        venue_id=uuid4(),
        event_date=date(2026, 8, 15),
        event_capacity=500,
        venue_aforo=400,
        tickets_sold=200,
        tickets_redeemed=180,
        revenue_cents=20_000_000,
        sellthrough_pct=40.0,
        occupancy_pct=45.0,
        average_ticket_cents=average_ticket_cents(20_000_000, 200),
    )
    assert row.average_ticket_cents == 100_000


def test_empty_sales_summary_has_no_fake_average() -> None:
    summary = summarize_sales([], grain="period")
    assert summary.order_or_ticket_count == 0
    assert summary.revenue_cents == 0
    assert summary.average_ticket_cents is None


def test_compare_summaries_on_empty_previous() -> None:
    current = summarize_sales(
        [SalesPoint(uuid4(), date(2026, 8, 1), 3, 300, uuid4())],
        grain="period",
    )
    previous = summarize_sales([], grain="period")
    compared = compare_summaries(current, previous)
    assert compared.revenue_change_pct is None
    assert compared.volume_change_pct is None
