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
        "Conteo de tickets redimidos (o hecho seed equivalente), agrupado por venue y fecha. "
        "Proxy de puerta; no incluye walk-in sin recaudo."
    ),
    as_of=None,
    data_quality="missing",
)

SALES_BY_NIGHT = MeasureMeta(
    name="sales_by_night",
    title="Ventas por noche",
    unit="orders_and_cents",
    definition=(
        "Órdenes y revenue en centavos por venue y noche. En modo seed lee fact_sales_by_night; "
        "en modo discover lee analytics.v_sales_by_night sobre orders de Discover."
    ),
    as_of=None,
    data_quality="missing",
)

ATTENDANCE_BY_GENDER = MeasureMeta(
    name="attendance_by_gender",
    title="Mix de género",
    unit="headcount",
    definition=(
        "Distribución de asistencia por género autodeclarado (woman / man / other / undisclosed). "
        "En seed usa fact_attendance_by_gender; no expone identidad de personas."
    ),
    as_of=None,
    data_quality="missing",
)

EVENT_PERFORMANCE = MeasureMeta(
    name="event_performance",
    title="Desempeño por evento",
    unit="mixto",
    definition=(
        "Desempeño derivado de cada evento (una noche en un venue). Une dim_event a los "
        "hechos por-noche existentes sobre (account_id, venue_id, event_date = night_date): "
        "tickets redimidos, órdenes y revenue, y mix de género. No hay tabla física de "
        "hechos por evento; se lee de la vista analytics.v_event_performance."
    ),
    as_of=None,
    data_quality="missing",
)

GenderCode = Literal["woman", "man", "other", "undisclosed"]


@dataclass(frozen=True)
class EventPerformance:
    event_id: UUID
    account_id: UUID
    venue_id: UUID
    name: str
    event_type: str
    event_date: date
    redeemed_tickets: int | None = None
    order_count: int | None = None
    revenue_cents: int | None = None
    headcount_woman: int | None = None
    headcount_man: int | None = None
    headcount_other: int | None = None
    headcount_undisclosed: int | None = None
    headcount_total: int | None = None


def quality_for_event_performance(perf: EventPerformance | None) -> Quality:
    """Calidad del desempeño derivado de un evento.

    missing: no hay evento o no hay ningún hecho por-noche asociado.
    partial: hay hechos pero falta alguna métrica (asistencia, ventas o género).
    ok: asistencia, ventas y género están presentes.
    """
    if perf is None:
        return "missing"
    if perf.redeemed_tickets is None and perf.order_count is None and perf.headcount_total is None:
        return "missing"
    if (
        perf.redeemed_tickets is None
        or perf.order_count is None
        or perf.revenue_cents is None
        or perf.headcount_total is None
    ):
        return "partial"
    return "ok"


@dataclass(frozen=True)
class AttendancePoint:
    venue_id: UUID
    night_date: date
    redeemed_tickets: int
    account_id: UUID | None = None


@dataclass(frozen=True)
class GenderPoint:
    gender: GenderCode
    headcount: int
    share: float
    account_id: UUID | None = None


def quality_for_points(points: list[AttendancePoint]) -> Quality:
    if not points:
        return "missing"
    if any(point.redeemed_tickets == 0 for point in points):
        return "partial"
    return "ok"


def quality_for_gender(points: list[GenderPoint]) -> Quality:
    if not points:
        return "missing"
    if any(point.headcount == 0 for point in points):
        return "partial"
    return "ok"
