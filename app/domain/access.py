from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AccessScope:
    """Resolved tenant window for a request.

    Empty venue_ids / event_ids means "all in the account" unless event_scoped.
    tenant_filter=False is for anonymous market views: do not add account_id
    (or any tenant identifier) to the query. Those views have no IDs in output.
    """

    account_id: UUID | None
    account_ids: frozenset[UUID]
    venue_ids: frozenset[UUID]
    event_ids: frozenset[UUID]
    event_scoped: bool
    allow_market_aggregates: bool
    tenant_filter: bool = True
