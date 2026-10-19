"""Static contracts for SQL views: tenant, privacy, COP, COUNT(tickets)."""

from pathlib import Path

VIEWS_DIR = Path(__file__).resolve().parents[1] / "sql" / "views"

PII_FRAGMENTS = (
    "email",
    "phone",
    "password",
    "document_id",
    "full_name",
    "first_name",
    "last_name",
)

REQUIRED_VIEWS = (
    "001_v_nightly_attendance.sql",
    "002_v_sales_by_night.sql",
    "003_v_ticket_sales_by_night.sql",
    "004_v_event_metrics.sql",
    "005_v_sellthrough_by_tier.sql",
    "006_v_sales_velocity.sql",
    "007_v_purchase_hours.sql",
    "008_v_buyer_mix_by_event.sql",
    "009_v_buyer_mix_by_month.sql",
    "010_v_activity_by_weekday.sql",
    "011_v_venues_normalized.sql",
    "012_v_market_by_city.sql",
    "013_v_market_by_venue_type.sql",
    "014_v_market_by_weekday.sql",
    "015_v_market_by_price_band.sql",
)

MARKET_VIEWS = (
    "012_v_market_by_city.sql",
    "013_v_market_by_venue_type.sql",
    "014_v_market_by_weekday.sql",
    "015_v_market_by_price_band.sql",
)


def _sql_files() -> list[Path]:
    return sorted(VIEWS_DIR.glob("*.sql"))


def _read(name: str) -> str:
    return (VIEWS_DIR / name).read_text(encoding="utf-8")


def _sql_body(sql: str) -> str:
    """Strip -- comments so contracts inspect executable SQL only."""
    lines: list[str] = []
    for raw in sql.splitlines():
        stripped = raw.split("--", 1)[0].strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines).lower()


def test_expected_views_exist() -> None:
    names = {path.name for path in _sql_files()}
    assert set(REQUIRED_VIEWS) == names
    assert len(REQUIRED_VIEWS) == 15
    assert "011_v_promoter_performance.sql" not in names
    assert "010_v_promo_performance.sql" not in names


def test_every_view_is_read_only_and_tenant_scoped() -> None:
    for path in _sql_files():
        sql = path.read_text(encoding="utf-8").lower()
        assert "create or replace view analytics." in sql, path.name
        assert "account_id" in sql, path.name
        assert "insert " not in sql
        assert "update " not in sql
        assert "delete " not in sql


def test_views_do_not_select_pii() -> None:
    for path in _sql_files():
        body = _sql_body(path.read_text(encoding="utf-8"))
        for fragment in PII_FRAGMENTS:
            assert fragment not in body, f"{path.name} mentions {fragment}"


def test_ticket_views_never_use_sold_quantity() -> None:
    for path in _sql_files():
        body = _sql_body(path.read_text(encoding="utf-8"))
        assert "sold_quantity" not in body, path.name


def test_ticket_sales_count_tickets_and_convert_cop_pesos() -> None:
    sql = _read("003_v_ticket_sales_by_night.sql")
    assert "COUNT(t.id)" in sql
    assert "* 100" in sql
    assert "price_paid_cop" in sql
    assert "canceled" in sql.lower()


def test_sales_by_night_filters_paid_orders_only() -> None:
    sql = _read("002_v_sales_by_night.sql")
    assert "COMPLETED" in sql
    assert "APPROVED" in sql
    assert "CONFIRMED_FREE" in sql
    assert "INITIAL_TRANSACTION" in sql  # documented as excluded
    assert "IN ('COMPLETED', 'CONFIRMED_FREE', 'APPROVED')" in sql
    assert "* 100" in sql


def test_sellthrough_uses_tier_capacity_not_batches() -> None:
    sql = _read("005_v_sellthrough_by_tier.sql")
    body = _sql_body(sql)
    assert "ticket_tiers" in sql
    assert "ticket_batches" not in body
    assert "COUNT(t.id)" in sql
    assert "tt.capacity" in sql


def test_buyer_mix_is_fail_closed_at_ten() -> None:
    for name in ("008_v_buyer_mix_by_event.sql", "009_v_buyer_mix_by_month.sql"):
        sql = _read(name)
        assert "HAVING COUNT(DISTINCT" in sql
        assert ">= 10" in sql
        assert "user_id" in sql  # used internally for DISTINCT counts
        assert " AS user_id" not in sql
        assert "buyer_count" in sql


def test_velocity_windows_match_domain() -> None:
    sql = _read("006_v_sales_velocity.sql")
    for key in ("early_bird", "week_before", "last_days", "same_day"):
        assert key in sql


def test_city_normalization_covers_medellin_variants() -> None:
    sql = _read("011_v_venues_normalized.sql")
    assert "medellin" in sql.lower()
    assert "city_normalized" in sql


def test_event_metrics_do_not_join_tiers_in_a_way_that_duplicates_tickets() -> None:
    sql = _read("004_v_event_metrics.sql")
    assert "LEFT JOIN ticket_tiers" not in sql
    assert "COUNT(t.id)" in sql
    assert "venues.aforo" in sql or "v.aforo" in sql
    assert "e.capacity" in sql


def test_market_views_are_anonymous_and_fail_closed() -> None:
    for name in MARKET_VIEWS:
        sql = _read(name)
        body = _sql_body(sql)
        assert " AS account_id" not in sql
        assert " AS venue_id" not in sql
        assert "sum(s.revenue_cents)" not in body.split("having")[-1]
        assert ">= 5" in sql
        assert ">= 3" in sql
        assert ">= 20" in sql
        assert "avg_tickets_per_venue" in sql
        assert "median_avg_ticket_cents" in sql
