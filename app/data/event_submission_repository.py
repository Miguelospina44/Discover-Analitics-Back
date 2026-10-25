"""Load, cache and filter sanitized event-form submissions."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.config import Settings, get_settings
from app.domain.event_submissions import (
    EventFormAccess,
    EventSubmission,
    EventSubmissionSummary,
    filter_submissions,
    load_collective_aliases,
    parse_sheet_rows,
    summarize_submissions,
    visible_submissions,
)
from app.infra.google_sheets import (
    FixtureSheetsReader,
    GoogleSheetsReadonlyClient,
    SheetsReader,
)

_FIXTURE_PATH = Path(__file__).resolve().parent / "event_form_fixture.json"
_DEFAULT_ALIASES = Path(__file__).resolve().parent / "collective_aliases.json"

@dataclass
class _Cache:
    key: str = ""
    loaded_at: float = 0.0
    loaded: bool = False
    rows: list[EventSubmission] | None = None


_cache_lock = threading.Lock()
_CACHE = _Cache()


class EventSubmissionRepository:
    def __init__(
        self,
        settings: Settings | None = None,
        reader: SheetsReader | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._reader = reader

    @property
    def is_demo(self) -> bool:
        return self._settings.event_form_source == "fixture"

    def _reader_or_default(self) -> SheetsReader:
        if self._reader is not None:
            return self._reader
        if self._settings.event_form_source == "fixture":
            return FixtureSheetsReader(_FIXTURE_PATH)
        credentials = (self._settings.google_sheets_credentials_file or "").strip()
        if not credentials:
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS_FILE requerido")
        return GoogleSheetsReadonlyClient(credentials)

    def _alias_path(self) -> Path:
        configured = (self._settings.collective_aliases_file or "").strip()
        return Path(configured) if configured else _DEFAULT_ALIASES

    def _range_a1(self) -> str:
        tab = self._settings.event_form_sheet_tab or "Respuestas de formulario 1"
        cells = self._settings.event_form_sheet_range or "A:M"
        return f"'{tab}'!{cells}"

    def load_all(self) -> list[EventSubmission]:
        settings = self._settings
        key = "|".join(
            (
                settings.event_form_source,
                settings.event_form_sheet_id or "fixture",
                self._range_a1(),
                str(self._alias_path()),
            )
        )
        ttl = max(1, settings.event_form_cache_ttl_seconds)
        now = time.monotonic()
        with _cache_lock:
            if _CACHE.loaded and _CACHE.key == key and now - _CACHE.loaded_at < ttl:
                return list(_CACHE.rows or [])

        values = self._reader_or_default().fetch_values(
            settings.event_form_sheet_id or "fixture",
            self._range_a1(),
        )
        aliases = load_collective_aliases(self._alias_path())
        rows = parse_sheet_rows(values, aliases)
        with _cache_lock:
            _CACHE.key = key
            _CACHE.loaded_at = time.monotonic()
            _CACHE.rows = list(rows)
            _CACHE.loaded = True
        return rows

    def list_visible(
        self,
        access: EventFormAccess,
        *,
        period_start: date | None = None,
        period_end: date | None = None,
        collective: str | None = None,
        presale: bool | None = None,
        commission: str | None = None,
    ) -> list[EventSubmission]:
        rows = visible_submissions(self.load_all(), access)
        return filter_submissions(
            rows,
            period_start=period_start,
            period_end=period_end,
            collective=collective,
            presale=presale,
            commission=commission,
        )

    def summarize(
        self,
        access: EventFormAccess,
        *,
        period_start: date | None = None,
        period_end: date | None = None,
        collective: str | None = None,
        presale: bool | None = None,
        commission: str | None = None,
    ) -> EventSubmissionSummary:
        rows = self.list_visible(
            access,
            period_start=period_start,
            period_end=period_end,
            collective=collective,
            presale=presale,
            commission=commission,
        )
        return summarize_submissions(
            rows,
            include_unmapped_count=access.kind == "all",
        )


def reset_event_submission_cache() -> None:
    with _cache_lock:
        _CACHE.key = ""
        _CACHE.loaded_at = 0.0
        _CACHE.rows = None
        _CACHE.loaded = False
