"""Audience cells: declared gender × age band, aggregates only.

Null or unknown gender/age become sin_dato. Nothing is invented.
k-anonymity folds cells under MIN_COHORT_SIZE into otros, or drops them.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.metric_definitions import MIN_COHORT_SIZE

GENDER_WOMAN = frozenset({"woman", "female", "mujer", "f", "femenino"})
GENDER_MAN = frozenset({"man", "male", "hombre", "m", "masculino"})
GENDER_OTHER = frozenset({"other", "otro", "non_binary", "non-binary", "nb", "no_binario"})

GENDER_SIN_DATO = "sin_dato"
AGE_SIN_DATO = "sin_dato"
OTROS = "otros"

AGE_BANDS: tuple[str, ...] = ("18-24", "25-34", "35-44", "45-54", "55+", AGE_SIN_DATO)
KNOWN_GENDERS: tuple[str, ...] = ("woman", "man", "other", GENDER_SIN_DATO)

DEMO_LABEL = "Datos de ejemplo (DATA_SOURCE=seed). No son filas de Discover."


@dataclass(frozen=True)
class AudienceCell:
    gender: str
    age_band: str
    headcount: int


def normalize_gender(raw: str | None) -> str:
    """Map a declared value to woman/man/other/sin_dato. Never guess."""
    if raw is None:
        return GENDER_SIN_DATO
    key = raw.strip().lower()
    if not key:
        return GENDER_SIN_DATO
    if key in GENDER_WOMAN:
        return "woman"
    if key in GENDER_MAN:
        return "man"
    if key in GENDER_OTHER:
        return "other"
    return GENDER_SIN_DATO


def age_band_from_years(years: int | None) -> str:
    """Band from a computed age. Under 18 or missing → sin_dato."""
    if years is None or years < 18:
        return AGE_SIN_DATO
    if years <= 24:
        return "18-24"
    if years <= 34:
        return "25-34"
    if years <= 44:
        return "35-44"
    if years <= 54:
        return "45-54"
    return "55+"


def apply_k_anonymity(
    cells: list[AudienceCell],
    minimum: int = MIN_COHORT_SIZE,
) -> list[AudienceCell]:
    """Hide small cohorts. Total < minimum → no rows. Small cells → otros or drop."""
    total = sum(cell.headcount for cell in cells)
    if total < minimum:
        return []
    kept: list[AudienceCell] = []
    folded = 0
    for cell in cells:
        if cell.headcount < minimum:
            folded += cell.headcount
        else:
            kept.append(cell)
    if folded >= minimum:
        kept.append(AudienceCell(gender=OTROS, age_band=OTROS, headcount=folded))
    return kept


def with_shares(cells: list[AudienceCell]) -> list[tuple[AudienceCell, float]]:
    total = sum(cell.headcount for cell in cells)
    if total <= 0:
        return []
    return [(cell, cell.headcount / total) for cell in cells]


SEED_DEMO_CELLS: tuple[AudienceCell, ...] = (
    AudienceCell("woman", "18-24", 28),
    AudienceCell("woman", "25-34", 41),
    AudienceCell("woman", "35-44", 22),
    AudienceCell("woman", "45-54", 14),
    AudienceCell("man", "18-24", 19),
    AudienceCell("man", "25-34", 36),
    AudienceCell("man", "35-44", 24),
    AudienceCell("man", "45-54", 12),
    AudienceCell("man", "55+", 11),
    AudienceCell("other", "25-34", 11),
    AudienceCell("sin_dato", "sin_dato", 18),
)
