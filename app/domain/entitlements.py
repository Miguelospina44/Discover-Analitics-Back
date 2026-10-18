from typing import Literal

PlanId = Literal["starter", "growth", "pro", "insight"]

PLANS: tuple[PlanId, ...] = ("starter", "growth", "pro", "insight")

# Technical keys. Product copy (Spanish) lives in ADR 0007.
PLAN_TITLES: dict[str, str] = {
    "starter": "Esencial",
    "growth": "Crecimiento",
    "pro": "Pro",
    "insight": "Insight",
}

# Entitlements accumulate: each plan includes the previous one.
_PLAN_OWN_ENTITLEMENTS: dict[str, frozenset[str]] = {
    "starter": frozenset(
        {
            "nightly_attendance",
            "sales_by_night",
            "market_aggregates",
            "venues",
        }
    ),
    "growth": frozenset(
        {
            "ticket_sales_by_night",
            "event_metrics",
            "sellthrough_by_tier",
            "attendance_by_gender",
        }
    ),
    "pro": frozenset(
        {
            "sales_velocity",
            "purchase_hours",
            "activity_by_weekday",
            "venues_normalized",
        }
    ),
    "insight": frozenset({"buyer_mix"}),
}

MEASURE_ENTITLEMENT: dict[str, str] = {
    "nightly_attendance": "nightly_attendance",
    "sales_by_night": "sales_by_night",
    "gremial_benchmarks": "market_aggregates",
    "attendance_by_gender": "attendance_by_gender",
    "ticket_sales_by_night": "ticket_sales_by_night",
    "event_metrics": "event_metrics",
    "sellthrough_by_tier": "sellthrough_by_tier",
    "sales_velocity": "sales_velocity",
    "purchase_hours": "purchase_hours",
    "activity_by_weekday": "activity_by_weekday",
    "venues_normalized": "venues_normalized",
    "buyer_mix_by_event": "buyer_mix",
    "buyer_mix_by_month": "buyer_mix",
}


def is_known_plan(plan: str) -> bool:
    return plan in _PLAN_OWN_ENTITLEMENTS


def entitlements_for_plan(plan: str) -> frozenset[str]:
    if not is_known_plan(plan):
        return frozenset()
    allowed: set[str] = set()
    for name in PLANS:
        allowed.update(_PLAN_OWN_ENTITLEMENTS[name])
        if name == plan:
            break
    return frozenset(allowed)


def entitlement_for_measure(measure: str) -> str:
    return MEASURE_ENTITLEMENT.get(measure, measure)


def plan_allows(plan: str, measure_or_entitlement: str) -> bool:
    key = entitlement_for_measure(measure_or_entitlement)
    return key in entitlements_for_plan(plan)
