from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.discover_views import (
    DISCOVER_VIEWS,
    FORBIDDEN_DISCOVER_COLUMNS,
    TENANT_IDENTIFIER_COLUMNS,
    discover_view_names,
    market_view_names,
)
from app.domain.entitlements import entitlements_for_plan, plan_allows
from app.domain.errors import ForbiddenError
from app.domain.principal import Principal


def _principal(**kwargs) -> Principal:
    defaults = {
        "user_id": uuid4(),
        "account_id": uuid4(),
        "role": "viewer",
        "email": "a@b.c",
        "tenant_kind": "venue",
        "plan": "growth",
    }
    defaults.update(kwargs)
    return Principal(**defaults)


def test_plans_accumulate() -> None:
    starter = entitlements_for_plan("starter")
    growth = entitlements_for_plan("growth")
    pro = entitlements_for_plan("pro")
    insight = entitlements_for_plan("insight")
    assert starter <= growth <= pro <= insight
    assert "buyer_mix" not in pro
    assert "buyer_mix" in insight
    assert "market_cross_tenant" not in pro
    assert "market_cross_tenant" in insight
    assert "nightly_attendance" in starter
    assert entitlements_for_plan("premium") == insight


def test_unknown_plan_is_fail_closed() -> None:
    assert entitlements_for_plan("enterprise") == frozenset()
    assert plan_allows("enterprise", "nightly_attendance") is False


def test_starter_blocks_gender_and_buyer_mix() -> None:
    principal = _principal(plan="starter")
    principal.require_entitlement("nightly_attendance")
    principal.require_entitlement("gremial_benchmarks")
    with pytest.raises(ForbiddenError):
        principal.require_entitlement("attendance_by_gender")
    with pytest.raises(ForbiddenError):
        principal.require_entitlement("buyer_mix_by_event")
    with pytest.raises(ForbiddenError):
        principal.require_entitlement("market_by_city")


def test_super_admin_bypasses_plan() -> None:
    principal = _principal(role="super_admin", plan="starter")
    principal.require_entitlement("buyer_mix_by_event")


def test_group_can_scope_child_account() -> None:
    parent = uuid4()
    child = uuid4()
    principal = _principal(
        account_id=parent,
        role="admin",
        tenant_kind="group",
        child_account_ids=frozenset({child}),
    )
    assert principal.resolve_account_scope(child) == child


def test_group_cannot_scope_unrelated_account() -> None:
    principal = _principal(role="admin", tenant_kind="group", child_account_ids=frozenset({uuid4()}))
    with pytest.raises(ForbiddenError):
        principal.resolve_account_scope(uuid4())


def test_collective_without_events_is_forbidden() -> None:
    principal = _principal(tenant_kind="collective", event_ids=frozenset())
    with pytest.raises(ForbiddenError, match="eventos"):
        principal.resolve_access_scope()
    with pytest.raises(ForbiddenError, match="local"):
        principal.require_entitlement("nightly_attendance")
    with pytest.raises(ForbiddenError, match="local"):
        principal.resolve_access_scope(measure="sales_by_night")


def test_collective_cannot_see_other_event() -> None:
    own = uuid4()
    principal = _principal(tenant_kind="collective", plan="insight", event_ids=frozenset({own}))
    scope = principal.resolve_access_scope(requested_event=own, measure="event_metrics")
    assert scope.event_scoped is True
    assert scope.event_ids == frozenset({own})
    assert scope.venue_ids == frozenset()
    with pytest.raises(ForbiddenError):
        principal.resolve_access_scope(requested_event=uuid4())


def test_collective_never_sees_venue_grain_even_with_events() -> None:
    own = uuid4()
    principal = _principal(
        tenant_kind="collective",
        plan="insight",
        event_ids=frozenset({own}),
        venue_ids=frozenset({uuid4()}),
    )
    for measure in (
        "nightly_attendance",
        "sales_by_night",
        "ticket_sales_by_night",
        "attendance_by_gender",
        "venues_normalized",
        "purchase_hours",
        "activity_by_weekday",
        "buyer_mix_by_month",
    ):
        with pytest.raises(ForbiddenError, match="local"):
            principal.require_entitlement(measure)
    with pytest.raises(ForbiddenError, match="local"):
        principal.resolve_access_scope(requested_venue=uuid4(), measure="event_metrics")
    principal.require_entitlement("event_metrics")
    principal.require_entitlement("sellthrough_by_tier")
    principal.require_entitlement("sales_velocity")
    principal.require_entitlement("buyer_mix_by_event")
    principal.require_entitlement("gremial_benchmarks")
    principal.require_entitlement("market_by_city")


def test_organizer_matches_collective_rules() -> None:
    principal = _principal(tenant_kind="organizer", plan="growth", event_ids=frozenset())
    with pytest.raises(ForbiddenError, match="local"):
        principal.require_entitlement("nightly_attendance")
    with pytest.raises(ForbiddenError, match="eventos"):
        principal.resolve_access_scope(measure="event_metrics")
    principal.require_entitlement("gremial_benchmarks")


def test_venue_scope_keeps_account_filter() -> None:
    account = uuid4()
    principal = _principal(account_id=account, tenant_kind="venue")
    scope = principal.resolve_access_scope()
    assert scope.account_id == account
    assert scope.event_scoped is False
    assert scope.allow_market_aggregates is True


def test_premium_unlocks_anonymous_market_views() -> None:
    principal = _principal(plan="premium")
    principal.require_entitlement("market_by_city")
    principal.require_entitlement("market_by_venue_type")
    principal.require_entitlement("market_by_weekday")
    principal.require_entitlement("market_by_price_band")
    scope = principal.resolve_market_scope()
    assert scope.tenant_filter is False
    assert scope.account_id is None
    assert scope.venue_ids == frozenset()
    assert scope.event_ids == frozenset()


def test_collective_without_events_can_read_market() -> None:
    principal = _principal(tenant_kind="collective", plan="insight", event_ids=frozenset())
    scope = principal.resolve_market_scope()
    assert scope.tenant_filter is False
    with pytest.raises(ForbiddenError, match="eventos"):
        principal.resolve_access_scope()


def test_fifteen_discover_views_have_no_pii_columns() -> None:
    names = discover_view_names()
    assert len(names) == 15
    assert names[0] == "analytics.v_nightly_attendance"
    assert names[-1] == "analytics.v_market_by_price_band"
    assert market_view_names() == (
        "analytics.v_market_by_city",
        "analytics.v_market_by_venue_type",
        "analytics.v_market_by_weekday",
        "analytics.v_market_by_price_band",
    )
    for view in DISCOVER_VIEWS:
        leaked = FORBIDDEN_DISCOVER_COLUMNS.intersection(view.columns)
        assert leaked == set(), f"{view.name} expone {leaked}"
        if not view.tenant_scoped:
            ids = TENANT_IDENTIFIER_COLUMNS.intersection(view.columns)
            assert ids == set(), f"{view.name} no debe exponer {ids}"


def test_readonly_sql_grants_the_allowlist() -> None:
    sql = Path("docs/discover-readonly-setup.sql").read_text(encoding="utf-8")
    for name in discover_view_names():
        assert f"GRANT SELECT ON {name} " in sql
    assert "GRANT SELECT ON public.users" not in sql
    assert "public.tickets" not in sql
