"""Event-form Sheets source: allowlist, aliases, access, cache, summary."""

import json
from datetime import date, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.data.event_submission_repository import (
    EventSubmissionRepository,
    reset_event_submission_cache,
)
from app.domain.errors import ForbiddenError
from app.domain.event_submissions import (
    ASSIGNED,
    UNASSIGNED,
    EventFormAccess,
    classify_header,
    filter_submissions,
    fold_text,
    is_forbidden_header,
    load_collective_aliases,
    normalize_commission,
    parse_presale,
    parse_sheet_rows,
    resolve_collective,
    resolve_event_form_access,
    summarize_submissions,
    visible_submissions,
)
from app.domain.principal import Principal
from app.infra.google_sheets import FixtureSheetsReader
from app.main import app

COFFEE = UUID("c3333333-3333-4333-8333-333333333301")
SELVA = UUID("c3333333-3333-4333-8333-333333333302")
FIXTURE = Path("app/data/event_form_fixture.json")

SENSITIVE_MARKERS = (
    "owner@coffee.example",
    "otro@coffee.example",
    "selva@example.com",
    "mystery@hidden.example",
    "selva2@example.com",
    "001122334455",
    "998877665544",
    "112233445566",
    "000111222333",
    "555666777888",
    "900123456-1",
    "1234567890",
    "800987654-3",
    "Bancolombia",
    "Davivienda",
    "BBVA",
)


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


def _fixture_values() -> list[list[str]]:
    return FixtureSheetsReader(FIXTURE).fetch_values("fixture", "A:M")


def _parsed():
    return parse_sheet_rows(_fixture_values(), load_collective_aliases())


def _assert_no_sensitive(payload: object) -> None:
    blob = json.dumps(payload, default=str, ensure_ascii=False)
    lowered = blob.lower()
    for marker in SENSITIVE_MARKERS:
        assert marker.lower() not in lowered, marker
    assert "correo electrónico" not in lowered
    assert "cuenta bancaria" not in lowered
    assert "cédula" not in lowered
    assert "cedula" not in lowered


def test_forbidden_headers_are_detected() -> None:
    assert is_forbidden_header("Dirección de correo electrónico")
    assert is_forbidden_header("Número de cuenta bancaria")
    assert is_forbidden_header("Banco")
    assert is_forbidden_header("Cédula / NIT")
    assert classify_header("Dirección de correo electrónico") is None
    assert classify_header("Marca temporal") == "submitted_at"
    assert classify_header("Fecha y hora del evento") == "event_at"
    assert classify_header("Medio de pago") == "payment_method"


def test_parser_drops_sensitive_columns() -> None:
    values = _fixture_values()
    raw_blob = json.dumps(values, ensure_ascii=False)
    assert "owner@coffee.example" in raw_blob
    rows = _parsed()
    public = [row.as_public_dict() for row in rows]
    _assert_no_sensitive(public)
    assert len(rows) == 5


def test_coffe_and_coffee_club_map_to_same_account() -> None:
    aliases = load_collective_aliases()
    first = resolve_collective("Coffe", aliases)
    second = resolve_collective("Coffee Club", aliases)
    assert first[0] == COFFEE
    assert second[0] == COFFEE
    assert first[1] == "Coffee Club"
    assert fold_text("Coffe") == "coffe"
    rows = _parsed()
    coffee_rows = [row for row in rows if row.account_id == COFFEE]
    assert len(coffee_rows) == 2
    assert all(row.assignment_status == ASSIGNED for row in coffee_rows)


def test_unmapped_collective_is_sin_asignar() -> None:
    row = next(item for item in _parsed() if item.collective_raw == "Los Random")
    assert row.account_id is None
    assert row.assignment_status == UNASSIGNED
    assert row.collective_name is None


def test_commission_11_5_is_kept() -> None:
    assert normalize_commission("11.5%") == "11.5"
    assert normalize_commission("11,5") == "11.5"
    assert normalize_commission("15%") == "15"
    assert normalize_commission("tarifa especial") == "tarifa especial"
    eleven = next(row for row in _parsed() if row.event_name == "Cierre de mes")
    assert eleven.commission == "11.5"


def test_crossed_presale_and_date_do_not_break() -> None:
    messy = next(row for row in _parsed() if row.event_name == "After raro")
    assert messy.has_presale is None
    assert messy.event_at is None
    assert messy.event_at_raw == "fecha cruzada"
    assert parse_presale("quizás") is None
    assert parse_presale("Sí") is True


def test_admin_sees_unmapped_collective_does_not() -> None:
    rows = _parsed()
    admin = visible_submissions(rows, EventFormAccess(kind="all", account_id=None))
    own = visible_submissions(rows, EventFormAccess(kind="own", account_id=COFFEE))
    assert len(admin) == 5
    assert any(row.assignment_status == UNASSIGNED for row in admin)
    assert len(own) == 2
    assert all(row.account_id == COFFEE for row in own)
    assert all(row.assignment_status == ASSIGNED for row in own)


def test_access_fail_closed_for_venues_and_groups() -> None:
    venue_admin = _principal(role="admin", tenant_kind="venue")
    group_viewer = _principal(role="viewer", tenant_kind="group")
    with pytest.raises(ForbiddenError, match="super_admin"):
        resolve_event_form_access(venue_admin)
    with pytest.raises(ForbiddenError, match="super_admin"):
        resolve_event_form_access(group_viewer)
    staff = _principal(role="super_admin", tenant_kind="venue")
    assert resolve_event_form_access(staff).kind == "all"
    collective = _principal(role="viewer", tenant_kind="collective", account_id=COFFEE)
    access = resolve_event_form_access(collective)
    assert access.kind == "own"
    assert access.account_id == COFFEE


def test_summary_kpis_and_11_5_bucket() -> None:
    rows = _parsed()
    summary = summarize_submissions(
        rows,
        now=datetime(2026, 10, 25, 12, 0, 0),
        include_unmapped_count=True,
    )
    assert summary.event_count == 5
    assert summary.collective_count == 2
    assert summary.presale_pct == 75.0
    assert summary.events_this_month == 2
    assert summary.unmapped_count == 1
    assert summary.top_collective == {"name": "Coffee Club", "event_count": 2}
    commissions = {item.key: item.count for item in summary.by_commission}
    assert commissions["11.5"] == 1
    assert commissions["tarifa especial"] == 1


def test_filters_by_presale_and_commission() -> None:
    rows = _parsed()
    only_presale = filter_submissions(rows, presale=True)
    assert {row.event_name for row in only_presale} == {
        "Martes de casa",
        "Selva viva",
        "Fecha sin mapa",
    }
    only_115 = filter_submissions(rows, commission="11.5%")
    assert [row.event_name for row in only_115] == ["Cierre de mes"]
    september = filter_submissions(
        rows, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)
    )
    assert len(september) == 2


def test_repository_cache_stores_sanitized_rows_only() -> None:
    reset_event_submission_cache()
    calls = {"n": 0}

    class _CountingReader:
        def fetch_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:
            calls["n"] += 1
            return _fixture_values()

    settings = Settings(_env_file=None, event_form_source="fixture")
    repo = EventSubmissionRepository(settings=settings, reader=_CountingReader())
    first = repo.load_all()
    second = repo.load_all()
    assert calls["n"] == 1
    assert first == second
    _assert_no_sensitive([row.as_public_dict() for row in first])
    reset_event_submission_cache()


def test_sheets_source_is_fail_closed_without_credentials() -> None:
    settings = Settings(
        _env_file=None,
        event_form_source="sheets",
        google_sheets_credentials_file=None,
        event_form_sheet_id=None,
    )
    errors = settings.validate_event_form_config()
    assert any("EVENT_FORM_SHEET_ID" in item for item in errors)
    assert any("GOOGLE_SHEETS_CREDENTIALS_FILE" in item for item in errors)
    blob = " ".join(errors)
    assert "private_key" not in blob


def test_fixture_source_does_not_need_google() -> None:
    settings = Settings(_env_file=None, event_form_source="fixture")
    assert settings.validate_event_form_config() == []


def test_endpoints_require_auth() -> None:
    with TestClient(app) as client:
        listing = client.get("/api/v1/event-submissions")
        summary = client.get("/api/v1/event-submissions/summary")
    assert listing.status_code == 401
    assert summary.status_code == 401
