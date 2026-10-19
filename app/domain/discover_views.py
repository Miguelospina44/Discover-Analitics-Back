from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoverView:
    name: str
    columns: tuple[str, ...]
    grain: str
    min_plan: str
    tenant_scoped: bool = True
    access_grain: str = "venue"


# Allowlist aligned with sql/views on the metrics PR (15 views). Output only.
# Views may join tickets.user_id internally; they must not expose it.
# tenant_scoped=False: cross-tenant market aggregates — no account/venue/event IDs.
DISCOVER_VIEWS: tuple[DiscoverView, ...] = (
    DiscoverView(
        name="analytics.v_nightly_attendance",
        columns=("account_id", "venue_id", "night_date", "redeemed_tickets"),
        grain="account + venue + night",
        min_plan="starter",
    ),
    DiscoverView(
        name="analytics.v_sales_by_night",
        columns=("account_id", "venue_id", "night_date", "order_count", "revenue_cents"),
        grain="account + venue + night",
        min_plan="starter",
    ),
    DiscoverView(
        name="analytics.v_ticket_sales_by_night",
        columns=("account_id", "venue_id", "night_date", "tickets_sold", "revenue_cents"),
        grain="account + venue + night",
        min_plan="growth",
    ),
    DiscoverView(
        name="analytics.v_event_metrics",
        columns=(
            "account_id",
            "event_id",
            "venue_id",
            "event_date",
            "event_capacity",
            "venue_aforo",
            "tickets_sold",
            "tickets_redeemed",
            "revenue_cents",
            "sellthrough_pct",
            "occupancy_pct",
        ),
        grain="account + event",
        min_plan="growth",
        access_grain="event",
    ),
    DiscoverView(
        name="analytics.v_sellthrough_by_tier",
        columns=(
            "account_id",
            "event_id",
            "venue_id",
            "tier_id",
            "tier_price_cop",
            "tier_capacity",
            "tickets_sold",
            "sellthrough_pct",
        ),
        grain="account + event + tier",
        min_plan="growth",
        access_grain="event",
    ),
    DiscoverView(
        name="analytics.v_sales_velocity",
        columns=(
            "account_id",
            "event_id",
            "venue_id",
            "event_date",
            "window_key",
            "tickets_sold",
            "revenue_cents",
        ),
        grain="account + event + window",
        min_plan="pro",
        access_grain="event",
    ),
    DiscoverView(
        name="analytics.v_purchase_hours",
        columns=("account_id", "event_id", "hour_of_day", "tickets_sold", "revenue_cents"),
        grain="account + event + hour",
        min_plan="pro",
        access_grain="event",
    ),
    DiscoverView(
        name="analytics.v_buyer_mix_by_event",
        columns=(
            "account_id",
            "event_id",
            "venue_id",
            "buyer_count",
            "new_buyers",
            "returning_buyers",
        ),
        grain="account + event (cohort >= 10)",
        min_plan="insight",
        access_grain="event",
    ),
    DiscoverView(
        name="analytics.v_buyer_mix_by_month",
        columns=("account_id", "order_month", "buyer_count", "new_buyers", "returning_buyers"),
        grain="account + month (cohort >= 10)",
        min_plan="insight",
    ),
    DiscoverView(
        name="analytics.v_activity_by_weekday",
        columns=("account_id", "iso_weekday", "tickets_sold", "revenue_cents"),
        grain="account + weekday",
        min_plan="pro",
    ),
    DiscoverView(
        name="analytics.v_venues_normalized",
        columns=(
            "account_id",
            "venue_id",
            "aforo",
            "city_raw",
            "city_normalized",
            "venue_type_normalized",
        ),
        grain="account + venue",
        min_plan="pro",
    ),
    DiscoverView(
        name="analytics.v_market_by_city",
        columns=(
            "city_normalized",
            "venues_in_sample",
            "accounts_in_sample",
            "avg_tickets_per_venue",
            "median_tickets_per_venue",
            "avg_revenue_cents_per_venue",
            "median_avg_ticket_cents",
        ),
        grain="city (cross-tenant, k-anon)",
        min_plan="insight",
        tenant_scoped=False,
        access_grain="market",
    ),
    DiscoverView(
        name="analytics.v_market_by_venue_type",
        columns=(
            "venue_type_normalized",
            "venues_in_sample",
            "accounts_in_sample",
            "avg_tickets_per_venue",
            "median_tickets_per_venue",
            "avg_revenue_cents_per_venue",
            "median_avg_ticket_cents",
        ),
        grain="venue type (cross-tenant, k-anon)",
        min_plan="insight",
        tenant_scoped=False,
        access_grain="market",
    ),
    DiscoverView(
        name="analytics.v_market_by_weekday",
        columns=(
            "iso_weekday",
            "venues_in_sample",
            "accounts_in_sample",
            "avg_tickets_per_venue",
            "median_tickets_per_venue",
            "avg_revenue_cents_per_venue",
            "median_avg_ticket_cents",
        ),
        grain="weekday (cross-tenant, k-anon)",
        min_plan="insight",
        tenant_scoped=False,
        access_grain="market",
    ),
    DiscoverView(
        name="analytics.v_market_by_price_band",
        columns=(
            "price_band",
            "venues_in_sample",
            "accounts_in_sample",
            "avg_tickets_per_venue",
            "median_tickets_per_venue",
            "avg_revenue_cents_per_venue",
            "median_avg_ticket_cents",
        ),
        grain="price band (cross-tenant, k-anon)",
        min_plan="insight",
        tenant_scoped=False,
        access_grain="market",
    ),
)

TENANT_IDENTIFIER_COLUMNS: frozenset[str] = frozenset(
    {"account_id", "venue_id", "event_id", "user_id", "tier_id"}
)

FORBIDDEN_DISCOVER_COLUMNS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "email",
        "phone",
        "user_id",
        "document",
        "full_name",
        "name",
        "ip",
        "card",
        "payment_method",
    }
)


def discover_view_names() -> tuple[str, ...]:
    return tuple(view.name for view in DISCOVER_VIEWS)


def market_view_names() -> tuple[str, ...]:
    return tuple(view.name for view in DISCOVER_VIEWS if not view.tenant_scoped)
