"""Tests for v1 metric definitions and formulas (no database)."""

from datetime import date
from uuid import uuid4

from app.data.metrics_repository import (
    SalesSummary,
    compare_summaries,
    group_sales_by_iso_weekday,
    group_sales_by_venue,
    summarize_sales,
)
from app.data.sales_repository import SalesPoint
from app.domain.metric_definitions import (
    CANCELED_TICKET_STATUSES,
    MIN_COHORT_SIZE,
    MIN_MARKET_ACCOUNTS,
    MIN_MARKET_COHORT,
    MIN_MARKET_VENUES,
    PESOS_TO_CENTS,
    PRICE_BANDS,
    V1_METRICS,
    V2_METRICS,
    V2_PRIORITY,
    VALID_ORDER_STATUSES,
    VELOCITY_WINDOWS,
    average_ticket_cents,
    buyer_mix,
    cents_to_pesos,
    is_canceled_ticket_status,
    is_paid_order_status,
    metric_by_key,
    normalize_city,
    normalize_venue_type,
    occupancy_pct,
    period_change_pct,
    pesos_to_cents,
    price_band,
    sales_window,
    sellthrough_pct,
    suppress_market_cell,
    suppress_small_cohort,
)


def test_v1_catalog_is_complete_for_owners() -> None:
    keys = {item.key for item in V1_METRICS}
    assert {
        "revenue",
        "average_ticket",
        "tickets_sold",
        "occupancy",
        "sellthrough_event",
        "sellthrough_tier",
        "sales_velocity",
        "event_comparison",
        "period_comparison",
        "venue_comparison",
        "buyer_mix",
        "purchase_peak_hours",
        "activity_by_weekday",
        "market_by_city",
        "market_by_venue_type",
        "market_by_weekday",
        "market_by_price_band",
    }.issubset(keys)


def test_every_v1_metric_has_executive_fields() -> None:
    for item in V1_METRICS:
        assert item.phase == "v1"
        assert item.title
        assert len(item.business_definition) > 40
        assert item.grain
        assert item.formula
        assert item.discover_source
        assert item.view_or_fact
        assert item.limitations
        assert item.privacy
        assert item.value_line in {"audience", "operations", "sales"}
        assert item.suggested_plan in {"basic", "intermediate", "premium"}
        assert item.applies_to
        assert "venue" in item.applies_to or "organizer" in item.applies_to


def test_value_lines_and_suggested_plans_cover_the_product() -> None:
    lines = {item.value_line for item in V1_METRICS}
    plans = {item.suggested_plan for item in V1_METRICS}
    assert lines == {"audience", "operations", "sales"}
    assert plans == {"basic", "intermediate", "premium"}
    assert metric_by_key("buyer_mix").value_line == "audience"
    assert metric_by_key("occupancy").value_line == "operations"
    assert metric_by_key("revenue").value_line == "sales"
    assert metric_by_key("revenue").suggested_plan == "basic"
    assert metric_by_key("market_by_city").suggested_plan == "premium"
    assert all(item.suggested_plan for item in V2_METRICS)


def test_v2_priority_covers_catalog_and_is_ordered() -> None:
    v2_keys = [item.key for item in V2_METRICS]
    assert set(V2_PRIORITY) == set(v2_keys)
    assert V2_PRIORITY[0] == "ads_roi"
    assert V2_PRIORITY[1] == "forecast_vs_actual"
    assert V2_PRIORITY[-1] == "buyer_geo"
    assert all(item.phase == "v2" for item in V2_METRICS)


def test_cop_pesos_are_not_treated_as_cents() -> None:
    cover_pesos = 85_000
    assert pesos_to_cents(cover_pesos) == 8_500_000
    assert cents_to_pesos(8_500_000) == 85_000
    assert PESOS_TO_CENTS == 100
    # 850 would be an implausible cover if someone already stored cents.
    assert cover_pesos != 850


def test_average_ticket_uses_integer_cents_and_rejects_zero_units() -> None:
    assert average_ticket_cents(1_000_000, 4) == 250_000
    assert average_ticket_cents(100, 0) is None
    assert average_ticket_cents(0, 5) == 0


def test_occupancy_and_sellthrough_formulas() -> None:
    assert occupancy_pct(80, 100) == 80.0
    assert occupancy_pct(80, None) is None
    assert occupancy_pct(80, 0) is None
    assert sellthrough_pct(150, 200) == 75.0
    assert sellthrough_pct(0, 200) == 0.0
    assert sellthrough_pct(10, None) is None


def test_period_change_undefined_when_previous_is_zero() -> None:
    assert period_change_pct(120, 100) == 20.0
    assert period_change_pct(80, 100) == -20.0
    assert period_change_pct(50, 0) is None


def test_sales_velocity_windows() -> None:
    assert sales_window(14) == "early_bird"
    assert sales_window(8) == "early_bird"
    assert sales_window(7) == "week_before"
    assert sales_window(3) == "week_before"
    assert sales_window(2) == "last_days"
    assert sales_window(1) == "last_days"
    assert sales_window(0) == "same_day"
    assert sales_window(-1) == "same_day"
    assert VELOCITY_WINDOWS == ("early_bird", "week_before", "last_days", "same_day")


def test_order_and_ticket_status_rules() -> None:
    assert is_paid_order_status("COMPLETED")
    assert is_paid_order_status("APPROVED")
    assert is_paid_order_status("CONFIRMED_FREE")
    assert not is_paid_order_status("INITIAL_TRANSACTION")
    assert not is_paid_order_status("canceled")
    assert is_canceled_ticket_status("canceled")
    assert is_canceled_ticket_status("CANCELADO")
    assert is_canceled_ticket_status("cancelled")
    assert not is_canceled_ticket_status("active")
    assert not is_canceled_ticket_status("inactive")
    assert not is_canceled_ticket_status("activo")
    assert not is_canceled_ticket_status(None)
    assert "INITIAL_TRANSACTION" not in VALID_ORDER_STATUSES
    assert "canceled" in CANCELED_TICKET_STATUSES


def test_buyer_mix_privacy_floor() -> None:
    assert MIN_COHORT_SIZE == 10
    assert suppress_small_cohort(9) is True
    assert suppress_small_cohort(10) is False
    assert buyer_mix(3, 4) is None
    assert buyer_mix(4, 6) == (4, 6, 40.0)
    assert buyer_mix(0, 10) == (0, 10, 0.0)


def test_market_cell_is_fail_closed_on_venues_accounts_and_cohort() -> None:
    assert MIN_MARKET_VENUES == 5
    assert MIN_MARKET_ACCOUNTS == 3
    assert MIN_MARKET_COHORT == 20
    assert suppress_market_cell(venues=5, accounts=3, cohort=20) is False
    assert suppress_market_cell(venues=4, accounts=3, cohort=20) is True
    assert suppress_market_cell(venues=5, accounts=2, cohort=20) is True
    assert suppress_market_cell(venues=5, accounts=3, cohort=19) is True


def test_price_band_uses_cop_pesos() -> None:
    assert price_band(0) == "free"
    assert price_band(40_000) == "entry"
    assert price_band(85_000) == "high"
    assert price_band(200_000) == "premium_cover"
    assert PRICE_BANDS == ("free", "entry", "standard", "high", "premium_cover")
    assert normalize_venue_type("discotk") == "discoteca"
    assert normalize_venue_type("BAR") == "bar"
    assert normalize_venue_type(None) == "unknown"


def test_city_normalization_handles_dirty_casing() -> None:
    assert normalize_city("Medellín") == "Medellín"
    assert normalize_city("medellin") == "Medellín"
    assert normalize_city("Medellin") == "Medellín"
    assert normalize_city("BOGOTA") == "Bogotá"
    assert normalize_city("  Cali ") == "Cali"
    assert normalize_city("") is None
    assert normalize_city(None) is None


def test_summarize_and_compare_from_nightly_points() -> None:
    venue_a = uuid4()
    venue_b = uuid4()
    account = uuid4()
    points = [
        SalesPoint(venue_a, date(2026, 8, 1), 10, 1_000_000, account),
        SalesPoint(venue_b, date(2026, 8, 1), 5, 500_000, account),
        SalesPoint(venue_a, date(2026, 8, 2), 10, 1_000_000, account),
    ]
    period = summarize_sales(points, grain="period")
    assert period.order_or_ticket_count == 25
    assert period.revenue_cents == 2_500_000
    assert period.average_ticket_cents == 100_000

    venues = group_sales_by_venue(points)
    assert venues[0].venue_id == venue_a
    assert venues[0].order_or_ticket_count == 20
    assert venues[1].venue_id == venue_b

    weekdays = group_sales_by_iso_weekday(points)
    # 2026-08-01 Saturday=6, 2026-08-02 Sunday=7
    by_day = {row.iso_weekday: row for row in weekdays}
    assert by_day[6].tickets_or_orders == 15
    assert by_day[7].tickets_or_orders == 10

    previous = SalesSummary(10, 1_000_000, 100_000, "period")
    compared = compare_summaries(period, previous)
    assert compared.revenue_change_pct == 150.0
    assert compared.volume_change_pct == 150.0


def test_ticket_metrics_are_not_available_on_seed_facts() -> None:
    assert metric_by_key("tickets_sold").seed_available is False
    assert metric_by_key("occupancy").seed_available is False
    assert metric_by_key("sellthrough_tier").seed_available is False
    assert metric_by_key("buyer_mix").seed_available is False
    assert metric_by_key("revenue").seed_available is True


def test_sold_quantity_is_rejected_in_definitions() -> None:
    for item in V1_METRICS:
        blob = f"{item.formula} {item.limitations} {item.discover_source}".lower()
        if "sold_quantity" in blob:
            assert "nunca" in item.limitations.lower() or "never" in item.limitations.lower()
            assert "count" in item.formula.lower()
