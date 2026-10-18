"""v1 metric catalog and pure formulas for Discover Analytics.

Product copy is Spanish. Technical keys, grains, and view names are English.
Formulas here are the source of truth for tests; SQL views implement the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Quality = Literal["ok", "partial", "missing"]
MetricPhase = Literal["v1", "v2"]

# COP operational amounts are pesos. Analytics stores revenue_cents = pesos * 100.
PESOS_TO_CENTS = 100

# Fail-closed privacy: never return a buyer cohort smaller than this.
MIN_COHORT_SIZE = 10

# Paid orders only. Carts (INITIAL_TRANSACTION) and canceled are not sales.
VALID_ORDER_STATUSES = frozenset({"COMPLETED", "CONFIRMED_FREE", "APPROVED"})

# Dirty EN/ES enum on tickets.status — treat these as not sold.
CANCELED_TICKET_STATUSES = frozenset({"canceled", "cancelled", "cancelado"})

VELOCITY_WINDOWS = ("early_bird", "week_before", "last_days", "same_day")


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    title: str
    business_definition: str
    grain: str
    formula: str
    discover_source: str
    view_or_fact: str
    limitations: str
    privacy: str
    phase: MetricPhase
    seed_available: bool


def pesos_to_cents(pesos: int) -> int:
    return pesos * PESOS_TO_CENTS


def cents_to_pesos(cents: int) -> float:
    return cents / PESOS_TO_CENTS


def average_ticket_cents(revenue_cents: int, units: int) -> int | None:
    """Revenue / sold units. None when units is 0 (do not return 0 as a fake ticket)."""
    if units <= 0:
        return None
    return revenue_cents // units


def ratio_pct(numerator: int, denominator: int | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 2)


def occupancy_pct(redeemed_tickets: int, venue_aforo: int | None) -> float | None:
    """Door occupancy: redeemed tickets / physical aforo."""
    return ratio_pct(redeemed_tickets, venue_aforo)


def sellthrough_pct(tickets_sold: int, capacity: int | None) -> float | None:
    """Inventory sell-through: COUNT(tickets) / capacity. Never sold_quantity."""
    return ratio_pct(tickets_sold, capacity)


def period_change_pct(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def sales_window(days_before_event: int) -> str:
    if days_before_event > 7:
        return "early_bird"
    if days_before_event >= 3:
        return "week_before"
    if days_before_event >= 1:
        return "last_days"
    return "same_day"


def is_canceled_ticket_status(status: str | None) -> bool:
    if status is None:
        return False
    return status.lower() in CANCELED_TICKET_STATUSES


def is_paid_order_status(status: str | None) -> bool:
    if status is None:
        return False
    return status in VALID_ORDER_STATUSES


def suppress_small_cohort(count: int, minimum: int = MIN_COHORT_SIZE) -> bool:
    """True when the aggregate must be hidden (privacy fail-closed)."""
    return count < minimum


def buyer_mix(
    new_buyers: int,
    returning_buyers: int,
    *,
    minimum: int = MIN_COHORT_SIZE,
) -> tuple[int, int, float] | None:
    """Return (new, returning, new_pct) or None when below the cohort floor."""
    total = new_buyers + returning_buyers
    if suppress_small_cohort(total, minimum):
        return None
    return (new_buyers, returning_buyers, round((new_buyers / total) * 100, 2))


def normalize_city(city: str | None) -> str | None:
    if city is None:
        return None
    stripped = city.strip()
    if not stripped:
        return None
    table = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    key = stripped.translate(table).lower()
    mapping = {
        "medellin": "Medellín",
        "bogota": "Bogotá",
        "cali": "Cali",
        "barranquilla": "Barranquilla",
        "cartagena": "Cartagena",
    }
    return mapping.get(key, stripped)


V1_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="revenue",
        title="Ingresos",
        business_definition=(
            "Dinero recaudado por boletos vendidos, en pesos colombianos. "
            "Sirve para ver cuánto generó una noche, un evento o un venue."
        ),
        grain="noche, evento, venue o periodo (siempre con account_id)",
        formula=(
            "SUM(COALESCE(tickets.price_paid_cop, ticket_tiers.price_cop, "
            "events.price_cop, 0)); la vista guarda pesos * 100 como revenue_cents"
        ),
        discover_source="tickets.price_paid_cop, ticket_tiers.price_cop, events.price_cop",
        view_or_fact="analytics.v_ticket_sales_by_night / analytics.v_event_metrics",
        limitations=(
            "Unidad operativa es COP pesos, no centavos. En DEV el GMV por orders "
            "APPROVED es casi nulo; no mezclar transactions huérfanas. Eventos gratis "
            "quedan en 0. Fase A seed usa fact_sales_by_night (escala histórica distinta)."
        ),
        privacy="Solo totales de tenant. Sin filas de comprador ni ticket individual.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="average_ticket",
        title="Ticket promedio",
        business_definition=(
            "Precio medio pagado por boleto vendido (o por orden en el puente de orders). "
            "Permite comparar noches caras vs volumen."
        ),
        grain="mismo que ingresos (noche / evento / venue / periodo)",
        formula="revenue_cents / tickets_sold (o / order_count en v_sales_by_night)",
        discover_source="derivada de ingresos y COUNT(tickets)",
        view_or_fact="capa de dominio sobre v_ticket_sales_by_night o fact_sales_by_night",
        limitations=(
            "Indefinido si no hay unidades. Mezclar órdenes gratis y de pago baja el "
            "promedio. El puente por orders no distingue tiers en la misma orden."
        ),
        privacy="Agregado. No se expone el precio pagado por una persona.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="tickets_sold",
        title="Boletos vendidos",
        business_definition=(
            "Cantidad de boletos emitidos y no cancelados. Es el volumen real de venta, "
            "no el aforo ni el check-in."
        ),
        grain="noche, evento, venue, tier o periodo",
        formula=(
            "COUNT(tickets.id) WHERE status no está cancelado "
            "(canceled/cancelled/cancelado)"
        ),
        discover_source="tickets.status, tickets.event_id / tickets.tier",
        view_or_fact="analytics.v_ticket_sales_by_night / analytics.v_event_metrics",
        limitations=(
            "Nunca usar ticket_batches.sold_quantity ni un sold_quantity de tier "
            "(en DEV está en 0). Enum de status mezclado EN/ES. Covers sin event_id "
            "se agrupan por venue_id."
        ),
        privacy="Solo conteos. Sin identificadores de ticket ni de usuario.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="occupancy",
        title="Ocupación",
        business_definition=(
            "Porcentaje del aforo físico que realmente entró (boletos redimidos / aforo). "
            "Responde: ¿se llenó el local esa noche?"
        ),
        grain="evento o noche + venue",
        formula="COUNT(tickets con redemption_date) / venues.aforo * 100",
        discover_source="tickets.redemption_date, venues.aforo",
        view_or_fact="analytics.v_event_metrics.occupancy_pct / v_nightly_attendance",
        limitations=(
            "Indefinida si aforo es NULL o 0. Sin scanner QR, redemption_date queda "
            "vacío y la ocupación subestima la puerta. No captura walk-in sin ticket."
        ),
        privacy="Agregado de puerta. No lista quién ingresó.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="sellthrough_event",
        title="Sell-through del evento",
        business_definition=(
            "Porcentaje del cupo del evento que ya se vendió. Útil para saber si hay "
            "que empujar preventa o si el evento está cerrado."
        ),
        grain="evento",
        formula="COUNT(tickets vendidos) / events.capacity * 100",
        discover_source="tickets (COUNT), events.capacity",
        view_or_fact="analytics.v_event_metrics.sellthrough_pct",
        limitations=(
            "Si capacity es NULL se deja vacío (no se inventa aforo como cupo de "
            "inventario). Over-sale puede superar 100%. Eventos gratis pueden verse "
            "agotados con ingreso 0."
        ),
        privacy="Agregado por evento. Sin compradores.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="sellthrough_tier",
        title="Sell-through por etapa / tier",
        business_definition=(
            "Qué tan vendido está cada lista de precio (early bird, general, VIP). "
            "Ayuda a decidir cuándo subir de etapa."
        ),
        grain="ticket_tier dentro de un evento",
        formula="COUNT(tickets del tier) / ticket_tiers.capacity * 100",
        discover_source="tickets.tier, ticket_tiers.capacity, ticket_tiers.price_cop",
        view_or_fact="analytics.v_sellthrough_by_tier",
        limitations=(
            "Nunca usar sold_quantity. Si el cupo del tier es NULL, el porcentaje "
            "queda vacío. Un cambio de precio a mitad de venta no se versiona."
        ),
        privacy="Agregado por tier. Sin filas individuales.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="sales_velocity",
        title="Ritmo de venta antes del evento",
        business_definition=(
            "Cuántos boletos se vendieron con anticipación vs de último minuto. "
            "Ventanas: early_bird (>7 días), week_before (3-7), last_days (1-2), same_day."
        ),
        grain="evento + ventana temporal",
        formula="COUNT(tickets) agrupado por days_before = event.date - purchased_at::date",
        discover_source="tickets.purchased_at, events.date",
        view_or_fact="analytics.v_sales_velocity",
        limitations=(
            "Requiere purchased_at e events.date confiables. Timezone America/Bogota. "
            "Compras posteriores a la fecha del evento caen en same_day."
        ),
        privacy="Agregado por ventana. Sin timestamps individuales en la API de datos.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="event_comparison",
        title="Comparativo entre eventos",
        business_definition=(
            "Ranking de eventos del tenant por ingresos, boletos o sell-through "
            "en un periodo. Sirve para ver qué fechas o conceptos funcionaron."
        ),
        grain="lista de eventos del account",
        formula="mismas fórmulas de ingresos / boletos / sell-through, ordenadas",
        discover_source="analytics.v_event_metrics",
        view_or_fact="analytics.v_event_metrics",
        limitations=(
            "Eventos de distinto aforo no son comparables en crudo; usar sell-through "
            "u ocupación para normalizar. Gratis rankean bajo en ingreso."
        ),
        privacy="Solo métricas de evento. Sin listado de asistentes.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="period_comparison",
        title="Comparativo entre periodos",
        business_definition=(
            "Variación de ingresos, órdenes o boletos frente al periodo anterior "
            "equivalente (semana a semana o mes a mes)."
        ),
        grain="dos rangos de fechas del mismo tenant",
        formula="(actual - anterior) / anterior * 100; indefinido si anterior = 0",
        discover_source=(
            "fact_sales_by_night (seed) o v_ticket_sales_by_night / v_sales_by_night"
        ),
        view_or_fact="capa de dominio sobre hechos/vistas diarias",
        limitations=(
            "Festivos y días de semana distintos sesgan WoW. Histórico corto en DEV "
            "(sandbox, no proxy de prod). No es estacionalidad ajustada."
        ),
        privacy="Totales de periodo. Sin personas.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="venue_comparison",
        title="Comparativo entre venues",
        business_definition=(
            "Mismo periodo, distintos locales del tenant: ingresos, ticket promedio "
            "y volumen para ver qué casa rinde más."
        ),
        grain="venue dentro de un account y periodo",
        formula="SUM ingresos y unidades GROUP BY venue_id",
        discover_source="v_ticket_sales_by_night o fact_sales_by_night",
        view_or_fact="capa de repositorio sobre vistas/hechos diarios",
        limitations=(
            "Un bar y una discoteca no se comparan en crudo (normalizar por aforo "
            "cuando exista). Un tenant de un solo venue no tiene contraste."
        ),
        privacy="Agregado por venue. Ciudades van normalizadas, no PII de compradores.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="buyer_mix",
        title="Compradores nuevos vs recurrentes",
        business_definition=(
            "Qué parte de la audiencia compra por primera vez en el tenant frente a "
            "quién ya había comprado antes. Solo retrato agregado."
        ),
        grain="evento o mes calendario",
        formula=(
            "new = users cuya primera compra del tenant es este evento/mes; "
            "returning = el resto; % = new / (new + returning)"
        ),
        discover_source="tickets.user_id + MIN(purchased_at) por tenant",
        view_or_fact="analytics.v_buyer_mix_by_event / analytics.v_buyer_mix_by_month",
        limitations=(
            "Invitados (user_id NULL) no entran. Sin historicidad larga todos parecen "
            "nuevos. No es LTV. Ciudades/roles de users.rol no se usan aquí."
        ),
        privacy=(
            f"Fail-closed: la vista no emite la fila si hay menos de "
            f"{MIN_COHORT_SIZE} compradores distintos. Nunca se selecciona user_id, "
            "email, teléfono ni nombre."
        ),
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="purchase_peak_hours",
        title="Horas pico de compra",
        business_definition=(
            "A qué hora del día (0-23, hora de Bogotá) se concentran las compras. "
            "Útil para pauta y para saber cuándo abrir preventa o recordatorios."
        ),
        grain="account + hora del día",
        formula="COUNT(tickets) GROUP BY EXTRACT(HOUR FROM purchased_at AT TIME ZONE Bogotá)",
        discover_source="tickets.purchased_at",
        view_or_fact="analytics.v_purchase_hours",
        limitations=(
            "No separa día laboral vs fin de semana (ver activity_by_weekday). "
            "Volumen bajo en DEV no forma un patrón estable."
        ),
        privacy="Histograma de 24 horas. Sin sesiones ni usuarios.",
        phase="v1",
        seed_available=False,
    ),
    MetricDefinition(
        key="activity_by_weekday",
        title="Actividad por día de semana",
        business_definition=(
            "Distribución de ventas según el día (lunes=1 … domingo=7). "
            "En vida nocturna suele concentrarse viernes-sábado."
        ),
        grain="account + iso_weekday",
        formula="COUNT(tickets) y SUM(revenue) GROUP BY ISODOW de purchased_at",
        discover_source="tickets.purchased_at",
        view_or_fact="analytics.v_activity_by_weekday (Discover) o hechos diarios (seed)",
        limitations="Festivos rompen el patrón. No sustituye un comparativo de fechas.",
        privacy="Siete buckets. Sin PII.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="nightly_attendance",
        title="Asistencia por noche",
        business_definition=(
            "Boletos redimidos en puerta por venue y noche. Proxy de asistencia real."
        ),
        grain="account + venue + night_date",
        formula="COUNT(tickets) WHERE redemption_date IS NOT NULL",
        discover_source="tickets.redemption_date, venues.account_id",
        view_or_fact="analytics.v_nightly_attendance / fact_nightly_attendance",
        limitations="Sin redención no hay señal de puerta. No incluye walk-in sin ticket.",
        privacy="Conteo de puerta. El mix de género vive en otra medida agregada.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="sales_by_night_orders",
        title="Ventas por noche (órdenes)",
        business_definition=(
            "Puente Fase B sobre orders pagadas: número de órdenes e ingreso. "
            "Complementa la métrica ticket a ticket; no la sustituye."
        ),
        grain="account + venue + night_date",
        formula=(
            "COUNT(orders) y SUM(total_amount)*100 WHERE order_status IN "
            f"{sorted(VALID_ORDER_STATUSES)}"
        ),
        discover_source="orders.total_amount, orders.order_status, orders.order_date",
        view_or_fact="analytics.v_sales_by_night / fact_sales_by_night",
        limitations=(
            "No mezclar transactions APPROVED (integridad rota en DEV). "
            "INITIAL_TRANSACTION no es venta. Preferir v_ticket_sales_by_night "
            "cuando exista price_paid_cop."
        ),
        privacy="Agregado de órdenes. Sin comprador.",
        phase="v1",
        seed_available=True,
    ),
    MetricDefinition(
        key="attendance_by_gender",
        title="Mix de género (agregado)",
        business_definition=(
            "Distribución de asistencia por género autodeclarado. Solo retrato de sala, "
            "nunca identidad."
        ),
        grain="account / venue / periodo",
        formula="SUM(headcount) y share por woman/man/other/undisclosed",
        discover_source="analytics.fact_attendance_detail (seed); Discover aún no modela género en tickets",
        view_or_fact="analytics.fact_attendance_detail",
        limitations=(
            "En Fase B Discover no hay vista de género hasta que exista el dato "
            "operacional. No cruzar con users individuales."
        ),
        privacy="Ya agregado. No exponer si se pidiera un cruce que baje de 10 personas.",
        phase="v1",
        seed_available=True,
    ),
)


V2_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="ads_roi",
        title="ROI de pauta",
        business_definition=(
            "Retorno de inversión publicitaria: ingreso atribuido vs gasto en Meta/Google."
        ),
        grain="campaña / periodo",
        formula="attributed_revenue / ad_spend",
        discover_source="no existe gasto ni API de ads; UTM en DEV es residual",
        view_or_fact="pendiente de fuente externa",
        limitations="UTM parcial no es ROI. Requiere integración de spend.",
        privacy="Agregar campañas; no perfiles de click.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="refund_rate",
        title="Tasa de cancelación / devolución",
        business_definition="Qué parte de lo vendido se anuló o reembolsó.",
        grain="evento / periodo",
        formula="refunded_tickets / tickets_sold",
        discover_source="no hay tabla refunds documentada",
        view_or_fact="pendiente",
        limitations="Hoy solo se excluyen status cancelados; no hay monto devuelto.",
        privacy="Agregado. Sin motivo individual.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="forecast_vs_actual",
        title="Proyección vs real",
        business_definition="Cumplimiento de la meta de venta o aforo que el dueño fijó.",
        grain="evento",
        formula="actual / forecast",
        discover_source="Discover no guarda forecast del organizador",
        view_or_fact="pendiente de captura en producto",
        limitations="Sin meta no hay % de cumplimiento.",
        privacy="Metas de negocio, no personas.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="buyer_ltv",
        title="Valor de vida del comprador (LTV)",
        business_definition="Ingreso acumulado por comprador recurrente a 6-12 meses.",
        grain="cohorte mensual anónima",
        formula="SUM(revenue) por user_id / buyers de la cohorte",
        discover_source="tickets.user_id + historicidad larga",
        view_or_fact="pendiente de ≥12 meses y umbral de cohorte más alto",
        limitations="DEV y Fase A no tienen profundidad. Riesgo de reidentificación si n es bajo.",
        privacy="Solo cohortes ≥20. Nunca LTV de un user_id expuesto.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="checkin_duration",
        title="Tiempo de check-in",
        business_definition="Cuánto tarda la fila de puerta (scan vs llegada).",
        grain="evento",
        formula="AVG(scan_at - queue_at)",
        discover_source="solo existe redemption_date; no hay timestamp de fila",
        view_or_fact="pendiente",
        limitations="Un unix de redención no mide espera.",
        privacy="Promedio de evento, no de persona.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="social_engagement",
        title="Interacciones en redes",
        business_definition="Alcance e interacciones de IG/FB asociadas al evento.",
        grain="evento / campaña",
        formula="depende de APIs de Meta",
        discover_source="fuera de Postgres Discover",
        view_or_fact="pendiente de integración",
        limitations="No hay tablas de redes en este repo.",
        privacy="Métricas de página, no de perfiles de asistentes.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="contribution_margin",
        title="Margen de contribución",
        business_definition="Ingreso menos costos variables del evento (artista, staff, pauta).",
        grain="evento",
        formula="revenue - variable_costs",
        discover_source="no hay módulo de gastos",
        view_or_fact="pendiente",
        limitations="Sin costos no hay margen.",
        privacy="Números de negocio del tenant.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="nps",
        title="NPS post-evento",
        business_definition="Recomendación de asistentes después de la noche.",
        grain="evento, solo si n ≥ umbral",
        formula="(% promotores - % detractores)",
        discover_source="no hay encuestas en Discover",
        view_or_fact="pendiente",
        limitations="Requiere producto de encuesta. Comentarios libres son PII.",
        privacy="Score agregado; no respuestas individuales.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="predictive_sellthrough",
        title="Sell-through predicho",
        business_definition="Estimación de agotamiento a partir del ritmo actual.",
        grain="evento / tier",
        formula="modelo sobre v_sales_velocity e histórico",
        discover_source="v1 es descriptivo; no hay modelo",
        view_or_fact="pendiente de historicidad y ML",
        limitations="Con sandbox DEV el modelo no es creíble.",
        privacy="Predicción de inventario, no de personas.",
        phase="v2",
        seed_available=False,
    ),
    MetricDefinition(
        key="buyer_geo",
        title="Origen geográfico de compradores",
        business_definition="Ciudades de residencia de quien compra, en agregado.",
        grain="evento, n ≥ 20",
        formula="COUNT DISTINCT users GROUP BY city normalizada",
        discover_source="users.city o IP; no está validado ni consentido",
        view_or_fact="pendiente de compliance",
        limitations="PII sensible. Ciudades de venues ya se normalizan; no es lo mismo.",
        privacy="Prohibido en v1. Si se hace, umbral ≥20 y sin barrios.",
        phase="v2",
        seed_available=False,
    ),
)


V2_PRIORITY: tuple[str, ...] = (
    "ads_roi",
    "forecast_vs_actual",
    "refund_rate",
    "buyer_ltv",
    "contribution_margin",
    "nps",
    "social_engagement",
    "checkin_duration",
    "predictive_sellthrough",
    "buyer_geo",
)


def metric_by_key(key: str) -> MetricDefinition:
    for item in (*V1_METRICS, *V2_METRICS):
        if item.key == key:
            return item
    raise KeyError(key)
