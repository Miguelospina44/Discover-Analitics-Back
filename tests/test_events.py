"""Fase C1: metadata-only checks for dim_event plus measure/quality units.

None of these require a database connection.
"""

from datetime import date
from uuid import uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.domain.measures import (
    EVENT_PERFORMANCE,
    EventPerformance,
    quality_for_event_performance,
)
from app.infra import orm

_EVENT_TYPES = ("regular", "especial", "privado", "festival", "otro")


def _perf(**overrides) -> EventPerformance:
    base = {
        "event_id": uuid4(),
        "account_id": uuid4(),
        "venue_id": uuid4(),
        "name": "Noche Demo",
        "event_type": "regular",
        "event_date": date(2026, 8, 1),
        "redeemed_tickets": 100,
        "order_count": 40,
        "revenue_cents": 500000,
        "headcount_woman": 50,
        "headcount_man": 45,
        "headcount_other": 3,
        "headcount_undisclosed": 2,
        "headcount_total": 100,
    }
    base.update(overrides)
    return EventPerformance(**base)


def test_dim_event_account_id_has_fk_restrict() -> None:
    fks = list(orm.DimEvent.__table__.c.account_id.foreign_keys)
    targets = {fk.target_fullname for fk in fks}
    assert "analytics.accounts.id" in targets
    for fk in fks:
        if fk.target_fullname == "analytics.accounts.id":
            assert fk.ondelete == "RESTRICT"


def test_dim_event_venue_id_fk_to_dim_venues() -> None:
    targets = {fk.target_fullname for fk in orm.DimEvent.__table__.c.venue_id.foreign_keys}
    assert "analytics.dim_venues.venue_id" in targets


def test_dim_event_type_check_matches_vocabulary() -> None:
    checks = [
        c for c in orm.DimEvent.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    type_checks = [c for c in checks if c.name == "ck_dim_event_type_allowed"]
    assert type_checks, "dim_event must declare ck_dim_event_type_allowed CHECK"
    sqltext = str(type_checks[0].sqltext)
    for event_type in _EVENT_TYPES:
        assert f"'{event_type}'" in sqltext


def test_dim_event_unique_venue_date_name() -> None:
    uniques = [
        c for c in orm.DimEvent.__table__.constraints if isinstance(c, UniqueConstraint)
    ]
    cols = [tuple(c.columns.keys()) for c in uniques]
    assert ("venue_id", "event_date", "name") in cols


def test_event_measure_meta_exists() -> None:
    assert EVENT_PERFORMANCE.name == "event_performance"
    assert EVENT_PERFORMANCE.title


def test_quality_missing_when_no_event() -> None:
    assert quality_for_event_performance(None) == "missing"


def test_quality_missing_when_no_facts() -> None:
    perf = _perf(
        redeemed_tickets=None,
        order_count=None,
        revenue_cents=None,
        headcount_woman=None,
        headcount_man=None,
        headcount_other=None,
        headcount_undisclosed=None,
        headcount_total=None,
    )
    assert quality_for_event_performance(perf) == "missing"


def test_quality_partial_when_missing_sales() -> None:
    perf = _perf(order_count=None, revenue_cents=None)
    assert quality_for_event_performance(perf) == "partial"


def test_quality_ok_when_all_present() -> None:
    assert quality_for_event_performance(_perf()) == "ok"
