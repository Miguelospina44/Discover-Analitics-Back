from typing import Literal

AccessGrain = Literal["venue", "event", "market"]

PlanId = Literal["starter", "growth", "pro", "insight"]

PLANS: tuple[PlanId, ...] = ("starter", "growth", "pro", "insight")

# Dictionary on the metrics PR uses basic / intermediate / premium.
PLAN_ALIASES: dict[str, PlanId] = {
    "basic": "starter",
    "intermediate": "growth",
    "premium": "insight",
}

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
            "audience_by_gender_age",
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
    "insight": frozenset({"buyer_mix", "market_cross_tenant"}),
}

MEASURE_ENTITLEMENT: dict[str, str] = {
    "nightly_attendance": "nightly_attendance",
    "sales_by_night": "sales_by_night",
    "gremial_benchmarks": "market_aggregates",
    "attendance_by_gender": "attendance_by_gender",
    "audience_by_gender_age": "audience_by_gender_age",
    "ticket_sales_by_night": "ticket_sales_by_night",
    "event_metrics": "event_metrics",
    "sellthrough_by_tier": "sellthrough_by_tier",
    "sales_velocity": "sales_velocity",
    "purchase_hours": "purchase_hours",
    "activity_by_weekday": "activity_by_weekday",
    "venues_normalized": "venues_normalized",
    "buyer_mix_by_event": "buyer_mix",
    "buyer_mix_by_month": "buyer_mix",
    "market_by_city": "market_cross_tenant",
    "market_by_venue_type": "market_cross_tenant",
    "market_by_weekday": "market_cross_tenant",
    "market_by_price_band": "market_cross_tenant",
}

# Venue grain = operación del local. Collectives/organizers never get this.
_VENUE_GRAIN: frozenset[str] = frozenset(
    {
        "nightly_attendance",
        "sales_by_night",
        "ticket_sales_by_night",
        "attendance_by_gender",
        "venues",
        "venues_normalized",
        "purchase_hours",
        "activity_by_weekday",
        "buyer_mix_by_month",
    }
)
_EVENT_GRAIN: frozenset[str] = frozenset(
    {
        "event_metrics",
        "sellthrough_by_tier",
        "sales_velocity",
        "buyer_mix",
        "buyer_mix_by_event",
        "audience_by_gender_age",
    }
)
_MARKET_GRAIN: frozenset[str] = frozenset(
    {
        "market_aggregates",
        "market_cross_tenant",
        "gremial_benchmarks",
        "market_by_city",
        "market_by_venue_type",
        "market_by_weekday",
        "market_by_price_band",
    }
)


def canonical_plan(plan: str) -> str | None:
    if plan in _PLAN_OWN_ENTITLEMENTS:
        return plan
    return PLAN_ALIASES.get(plan)


def is_known_plan(plan: str) -> bool:
    return canonical_plan(plan) is not None


def entitlements_for_plan(plan: str) -> frozenset[str]:
    resolved = canonical_plan(plan)
    if resolved is None:
        return frozenset()
    allowed: set[str] = set()
    for name in PLANS:
        allowed.update(_PLAN_OWN_ENTITLEMENTS[name])
        if name == resolved:
            break
    return frozenset(allowed)


def entitlement_for_measure(measure: str) -> str:
    return MEASURE_ENTITLEMENT.get(measure, measure)


def plan_allows(plan: str, measure_or_entitlement: str) -> bool:
    key = entitlement_for_measure(measure_or_entitlement)
    return key in entitlements_for_plan(plan)


def access_grain(measure_or_entitlement: str) -> AccessGrain:
    if measure_or_entitlement in _MARKET_GRAIN:
        return "market"
    if measure_or_entitlement in _EVENT_GRAIN:
        return "event"
    if measure_or_entitlement in _VENUE_GRAIN:
        return "venue"
    key = entitlement_for_measure(measure_or_entitlement)
    if key in _MARKET_GRAIN:
        return "market"
    if key in _EVENT_GRAIN:
        return "event"
    return "venue"
