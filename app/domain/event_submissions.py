"""Event-form submissions from Google Sheets (or a local fixture).

Sensitive columns never leave the parser. Collective names map through an
alias table. Access: Discover staff (super_admin) sees all; a collective
sees only its mapped rows; venues/groups are forbidden.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.errors import ForbiddenError
from app.domain.principal import Principal
from app.domain.tenant import EVENT_SCOPED_KINDS

BOGOTA = ZoneInfo("America/Bogota")
DEMO_LABEL = (
    "Datos de ejemplo (EVENT_FORM_SOURCE=fixture). No son respuestas del Google Form real."
)
ASSIGNED = "mapped"
UNASSIGNED = "sin_asignar"

_DEFAULT_ALIASES = Path(__file__).resolve().parents[1] / "data" / "collective_aliases.json"

# Header matching is by folded text, not column letter (A:M can drift).
_ALLOWED_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "submitted_at": ("marca temporal", "timestamp", "marca de tiempo"),
    "event_at": ("fecha y hora del evento", "fecha del evento"),
    "collective_raw": ("nombre del colectivo", "colectivo u organizador", "colectivo"),
    "event_name": ("nombre del evento",),
    "flyer_url": ("flyers", "flyer"),
    "has_presale": ("preventa",),
    "commission": ("comision",),
    "exclusive_benefit": ("beneficio exclusivo", "beneficio"),
    "promotion_commitments": ("compromisos de promocion", "compromisos"),
    "payment_method": ("medio de pago", "metodo de pago"),
}

_YES = frozenset({"si", "yes", "true", "1", "s"})
_NO = frozenset({"no", "false", "0", "n"})

_DATE_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y",
)


def fold_text(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(ascii_only.lower().split())


def is_forbidden_header(header: str) -> bool:
    folded = fold_text(header)
    if not folded:
        return False
    if "correo" in folded or "email" in folded or "e-mail" in folded:
        return True
    if "cuenta" in folded:
        return True
    if "banco" in folded:
        return True
    if "cedula" in folded or "nit" in folded:
        return True
    return "documento" in folded or "identificacion" in folded


def classify_header(header: str) -> str | None:
    """Return an allowed field key, or None if the column is dropped."""
    if is_forbidden_header(header):
        return None
    folded = fold_text(header)
    for field_key, aliases in _ALLOWED_HEADER_ALIASES.items():
        for alias in aliases:
            if alias == folded or alias in folded:
                return field_key
    return None


def parse_datetime(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=BOGOTA)
        return parsed
    return None


def parse_presale(raw: str) -> bool | None:
    key = fold_text(raw)
    if not key:
        return None
    if key in _YES:
        return True
    if key in _NO:
        return False
    return None


def normalize_commission(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "sin_dato"
    compact = text.replace("%", "").replace(",", ".").strip()
    try:
        number = float(compact)
    except ValueError:
        return text
    if abs(number - round(number)) < 1e-9:
        return str(round(number))
    return f"{number:.10g}"


@dataclass(frozen=True)
class CollectiveAlias:
    account_id: UUID
    canonical_name: str
    aliases: frozenset[str]


@dataclass(frozen=True)
class EventSubmission:
    submitted_at: datetime | None
    event_at: datetime | None
    event_at_raw: str
    collective_raw: str
    collective_name: str | None
    account_id: UUID | None
    assignment_status: str
    event_name: str
    flyer_url: str
    has_presale: bool | None
    commission: str
    exclusive_benefit: str
    promotion_commitments: str
    payment_method: str

    def as_public_dict(self) -> dict:
        return {
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "event_at": self.event_at.isoformat() if self.event_at else None,
            "event_at_raw": self.event_at_raw,
            "collective_raw": self.collective_raw,
            "collective_name": self.collective_name,
            "account_id": str(self.account_id) if self.account_id else None,
            "assignment_status": self.assignment_status,
            "event_name": self.event_name,
            "flyer_url": self.flyer_url,
            "has_presale": self.has_presale,
            "commission": self.commission,
            "exclusive_benefit": self.exclusive_benefit,
            "promotion_commitments": self.promotion_commitments,
            "payment_method": self.payment_method,
        }


@dataclass(frozen=True)
class EventFormAccess:
    kind: Literal["all", "own"]
    account_id: UUID | None


def load_collective_aliases(path: Path | None = None) -> tuple[CollectiveAlias, ...]:
    source = path or _DEFAULT_ALIASES
    payload = json.loads(source.read_text(encoding="utf-8"))
    accounts: list[CollectiveAlias] = []
    for item in payload.get("accounts", []):
        aliases = {fold_text(alias) for alias in item.get("aliases", []) if fold_text(alias)}
        aliases.add(fold_text(item["canonical_name"]))
        accounts.append(
            CollectiveAlias(
                account_id=UUID(item["account_id"]),
                canonical_name=str(item["canonical_name"]),
                aliases=frozenset(aliases),
            )
        )
    return tuple(accounts)


def resolve_collective(
    raw_name: str, aliases: tuple[CollectiveAlias, ...]
) -> tuple[UUID | None, str | None, str]:
    key = fold_text(raw_name)
    if not key:
        return None, None, UNASSIGNED
    for item in aliases:
        if key in item.aliases:
            return item.account_id, item.canonical_name, ASSIGNED
    return None, None, UNASSIGNED


def parse_sheet_rows(
    values: list[list[str]],
    aliases: tuple[CollectiveAlias, ...],
) -> list[EventSubmission]:
    if not values:
        return []
    headers = [str(cell) for cell in values[0]]
    index_to_field: dict[int, str] = {}
    used_fields: set[str] = set()
    for index, header in enumerate(headers):
        if is_forbidden_header(header):
            continue
        field_key = classify_header(header)
        if field_key is None or field_key in used_fields:
            continue
        index_to_field[index] = field_key
        used_fields.add(field_key)

    rows: list[EventSubmission] = []
    for raw in values[1:]:
        mapped: dict[str, str] = {}
        for index, field_key in index_to_field.items():
            mapped[field_key] = str(raw[index]) if index < len(raw) and raw[index] is not None else ""
        collective_raw = mapped.get("collective_raw", "").strip()
        account_id, canonical, status = resolve_collective(collective_raw, aliases)
        rows.append(
            EventSubmission(
                submitted_at=parse_datetime(mapped.get("submitted_at", "")),
                event_at=parse_datetime(mapped.get("event_at", "")),
                event_at_raw=mapped.get("event_at", "").strip(),
                collective_raw=collective_raw,
                collective_name=canonical,
                account_id=account_id,
                assignment_status=status,
                event_name=mapped.get("event_name", "").strip(),
                flyer_url=mapped.get("flyer_url", "").strip(),
                has_presale=parse_presale(mapped.get("has_presale", "")),
                commission=normalize_commission(mapped.get("commission", "")),
                exclusive_benefit=mapped.get("exclusive_benefit", "").strip(),
                promotion_commitments=mapped.get("promotion_commitments", "").strip(),
                payment_method=mapped.get("payment_method", "").strip(),
            )
        )
    return rows


def resolve_event_form_access(principal: Principal) -> EventFormAccess:
    if principal.super_admin:
        return EventFormAccess(kind="all", account_id=None)
    if principal.tenant_kind in EVENT_SCOPED_KINDS:
        return EventFormAccess(kind="own", account_id=principal.account_id)
    raise ForbiddenError(
        "Solo el staff de Discover (super_admin) o el colectivo dueño pueden ver "
        "estas respuestas"
    )


def visible_submissions(
    rows: list[EventSubmission],
    access: EventFormAccess,
) -> list[EventSubmission]:
    if access.kind == "all":
        return list(rows)
    return [
        row
        for row in rows
        if row.assignment_status == ASSIGNED and row.account_id == access.account_id
    ]


def filter_submissions(
    rows: list[EventSubmission],
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    collective: str | None = None,
    presale: bool | None = None,
    commission: str | None = None,
) -> list[EventSubmission]:
    collective_key = fold_text(collective) if collective else ""
    commission_key = normalize_commission(commission) if commission else ""
    kept: list[EventSubmission] = []
    for row in rows:
        event_day = row.event_at.date() if row.event_at else None
        if period_start is not None and (event_day is None or event_day < period_start):
            continue
        if period_end is not None and (event_day is None or event_day > period_end):
            continue
        if collective_key:
            haystack = " ".join(
                part
                for part in (
                    fold_text(row.collective_raw),
                    fold_text(row.collective_name or ""),
                    str(row.account_id or ""),
                )
                if part
            )
            if collective_key not in haystack:
                continue
        if presale is not None and row.has_presale is not presale:
            continue
        if commission_key and row.commission != commission_key:
            continue
        kept.append(row)
    return kept


@dataclass(frozen=True)
class DistributionBucket:
    key: str
    count: int


@dataclass(frozen=True)
class EventSubmissionSummary:
    event_count: int
    collective_count: int
    presale_pct: float | None
    events_this_month: int
    top_collective: dict | None
    unmapped_count: int
    by_month: list[DistributionBucket] = field(default_factory=list)
    by_commission: list[DistributionBucket] = field(default_factory=list)
    by_presale: list[DistributionBucket] = field(default_factory=list)
    by_commitment: list[DistributionBucket] = field(default_factory=list)
    by_benefit: list[DistributionBucket] = field(default_factory=list)
    by_payment_method: list[DistributionBucket] = field(default_factory=list)


def _buckets(values: list[str]) -> list[DistributionBucket]:
    counts: dict[str, int] = {}
    for value in values:
        key = value or "sin_dato"
        counts[key] = counts.get(key, 0) + 1
    return [
        DistributionBucket(key=key, count=counts[key])
        for key in sorted(counts, key=lambda item: (-counts[item], item))
    ]


def summarize_submissions(
    rows: list[EventSubmission],
    *,
    now: datetime | None = None,
    include_unmapped_count: bool = False,
) -> EventSubmissionSummary:
    clock = now or datetime.now(BOGOTA)
    month_key = clock.strftime("%Y-%m")
    mapped = [row for row in rows if row.assignment_status == ASSIGNED]
    collective_ids = {row.account_id for row in mapped if row.account_id is not None}
    answered = [row for row in rows if row.has_presale is not None]
    presale_yes = sum(1 for row in answered if row.has_presale)
    presale_pct = round(100.0 * presale_yes / len(answered), 1) if answered else None
    events_this_month = sum(
        1 for row in rows if row.event_at and row.event_at.strftime("%Y-%m") == month_key
    )
    name_counts: dict[str, int] = {}
    for row in mapped:
        name = row.collective_name or row.collective_raw
        name_counts[name] = name_counts.get(name, 0) + 1
    top = None
    if name_counts:
        winner = max(sorted(name_counts), key=lambda name: name_counts[name])
        top = {"name": winner, "event_count": name_counts[winner]}

    def month_of(row: EventSubmission) -> str:
        if row.event_at:
            return row.event_at.strftime("%Y-%m")
        return "sin_dato"

    def presale_key(row: EventSubmission) -> str:
        if row.has_presale is True:
            return "si"
        if row.has_presale is False:
            return "no"
        return "sin_dato"

    return EventSubmissionSummary(
        event_count=len(rows),
        collective_count=len(collective_ids),
        presale_pct=presale_pct,
        events_this_month=events_this_month,
        top_collective=top,
        unmapped_count=sum(1 for row in rows if row.assignment_status == UNASSIGNED)
        if include_unmapped_count
        else 0,
        by_month=_buckets([month_of(row) for row in rows]),
        by_commission=_buckets([row.commission for row in rows]),
        by_presale=_buckets([presale_key(row) for row in rows]),
        by_commitment=_buckets([row.promotion_commitments for row in rows]),
        by_benefit=_buckets([row.exclusive_benefit for row in rows]),
        by_payment_method=_buckets([row.payment_method for row in rows]),
    )


def as_of_date() -> date:
    return datetime.now(UTC).date()
