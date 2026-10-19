"""Audience by gender × age: k-anonymity, sin_dato, seed demo, organizer scope."""

from datetime import date
from uuid import uuid4

import pytest

from app.data.audience_repository import AudienceRepository
from app.domain.analytics_scope import organizer_scope, venue_scope
from app.domain.audience import (
    DEMO_LABEL,
    SEED_DEMO_CELLS,
    AudienceCell,
    age_band_from_years,
    apply_k_anonymity,
    normalize_gender,
)
from app.domain.entitlements import access_grain
from app.domain.errors import ForbiddenError
from app.domain.metric_definitions import MIN_COHORT_SIZE, applies_to_actor, metric_by_key
from app.domain.principal import Principal


class _SeedSettings:
    uses_seed_facts = True
    uses_discover_source = False
    data_source = "seed"


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


def test_normalize_gender_does_not_invent() -> None:
    assert normalize_gender(None) == "sin_dato"
    assert normalize_gender("") == "sin_dato"
    assert normalize_gender("  ") == "sin_dato"
    assert normalize_gender("unknown") == "sin_dato"
    assert normalize_gender("undisclosed") == "sin_dato"
    assert normalize_gender("prefer_not_to_say") == "sin_dato"
    assert normalize_gender("mujer") == "woman"
    assert normalize_gender("MALE") == "man"
    assert normalize_gender("non_binary") == "other"


def test_age_bands_and_under_eighteen_are_sin_dato() -> None:
    assert age_band_from_years(None) == "sin_dato"
    assert age_band_from_years(17) == "sin_dato"
    assert age_band_from_years(18) == "18-24"
    assert age_band_from_years(24) == "18-24"
    assert age_band_from_years(25) == "25-34"
    assert age_band_from_years(44) == "35-44"
    assert age_band_from_years(54) == "45-54"
    assert age_band_from_years(55) == "55+"
    assert age_band_from_years(80) == "55+"


def test_k_anonymity_hides_total_below_ten() -> None:
    cells = [
        AudienceCell("woman", "18-24", 4),
        AudienceCell("man", "25-34", 5),
    ]
    assert apply_k_anonymity(cells) == []
    assert MIN_COHORT_SIZE == 10


def test_k_anonymity_folds_small_cells_into_otros_when_residual_reaches_floor() -> None:
    cells = [
        AudienceCell("woman", "18-24", 40),
        AudienceCell("man", "25-34", 3),
        AudienceCell("sin_dato", "sin_dato", 4),
        AudienceCell("other", "55+", 5),
    ]
    published = apply_k_anonymity(cells)
    genders = {cell.gender for cell in published}
    assert "woman" in genders
    assert "man" not in genders
    otros = next(cell for cell in published if cell.gender == "otros")
    assert otros.age_band == "otros"
    assert otros.headcount == 12


def test_k_anonymity_drops_small_residual_instead_of_leaking() -> None:
    cells = [
        AudienceCell("woman", "18-24", 40),
        AudienceCell("man", "25-34", 3),
    ]
    published = apply_k_anonymity(cells)
    assert [cell.gender for cell in published] == ["woman"]
    assert all(cell.headcount >= 10 for cell in published)


@pytest.mark.asyncio
async def test_seed_path_is_marked_demo_and_passes_k_anonymity() -> None:
    account = uuid4()
    repo = AudienceRepository(session=None, settings=_SeedSettings())  # type: ignore[arg-type]
    result = await repo.list_gender_age(
        account, date(2026, 8, 1), date(2026, 8, 14), scope=venue_scope(account)
    )
    assert result.is_demo is True
    assert result.demo_label == DEMO_LABEL
    assert result.quality == "ok"
    assert result.points
    assert all(point.headcount >= 10 for point in result.points)
    assert {cell.gender for cell in SEED_DEMO_CELLS} <= {
        point.gender for point in result.points
    }
    assert any(point.gender == "sin_dato" for point in result.points)
    assert "user_id" not in {point.gender for point in result.points}


@pytest.mark.asyncio
async def test_organizer_without_events_gets_no_seed_rows() -> None:
    account = uuid4()
    repo = AudienceRepository(session=None, settings=_SeedSettings())  # type: ignore[arg-type]
    result = await repo.list_gender_age(
        account,
        date(2026, 8, 1),
        date(2026, 8, 14),
        scope=organizer_scope(account, frozenset()),
    )
    assert result.points == []
    assert result.is_demo is True
    assert result.quality == "missing"


@pytest.mark.asyncio
async def test_organizer_with_events_gets_demo_aggregates_not_venue_ids() -> None:
    account = uuid4()
    repo = AudienceRepository(session=None, settings=_SeedSettings())  # type: ignore[arg-type]
    result = await repo.list_gender_age(
        account,
        date(2026, 8, 1),
        date(2026, 8, 14),
        venue_id=uuid4(),
        scope=organizer_scope(account, {uuid4()}),
    )
    assert result.is_demo is True
    assert result.points
    assert all(hasattr(point, "gender") and hasattr(point, "age_band") for point in result.points)


def test_catalog_and_entitlement_are_event_grain() -> None:
    assert applies_to_actor("audience_by_gender_age", "organizer")
    assert applies_to_actor("audience_by_gender_age", "venue")
    assert metric_by_key("audience_by_gender_age").view_or_fact.endswith(
        "v_audience_by_gender_age"
    )
    assert access_grain("audience_by_gender_age") == "event"


def test_collective_can_read_audience_with_events_but_not_without() -> None:
    own = uuid4()
    principal = _principal(
        tenant_kind="collective",
        plan="growth",
        event_ids=frozenset({own}),
    )
    scope = principal.resolve_access_scope(measure="audience_by_gender_age")
    assert scope.event_scoped is True
    assert scope.event_ids == frozenset({own})
    assert scope.venue_ids == frozenset()
    empty = _principal(tenant_kind="collective", plan="growth", event_ids=frozenset())
    with pytest.raises(ForbiddenError, match="eventos"):
        empty.resolve_access_scope(measure="audience_by_gender_age")
    with pytest.raises(ForbiddenError, match="local"):
        principal.resolve_access_scope(
            requested_venue=uuid4(), measure="audience_by_gender_age"
        )
