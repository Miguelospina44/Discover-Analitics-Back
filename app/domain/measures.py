from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

Quality = Literal["ok", "partial", "missing"]


@dataclass(frozen=True)
class MeasureMeta:
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: Quality


NIGHTLY_ATTENDANCE = MeasureMeta(
    name="nightly_attendance",
    title="Asistencia por noche",
    unit="tickets_redimidos",
    definition=(
        "Conteo de tickets con redemption_date, agrupado por establecimiento y fecha local. "
        "Es un proxy de puerta, no aforo físico ni walk-in sin recaudo."
    ),
    as_of=None,
    data_quality="missing",
)


@dataclass(frozen=True)
class AttendancePoint:
    venue_id: UUID
    night_date: date
    redeemed_tickets: int


def quality_for_points(points: list[AttendancePoint]) -> Quality:
    if not points:
        return "missing"
    if any(point.redeemed_tickets == 0 for point in points):
        return "partial"
    return "ok"
