from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AccessScope:
    """Resolved tenant window for a request.

    Empty venue_ids / event_ids means "all in the account" unless event_scoped.
    account_id is None only for staff (super_admin) reading the whole market.
    """

    account_id: UUID | None
    account_ids: frozenset[UUID]
    venue_ids: frozenset[UUID]
    event_ids: frozenset[UUID]
    event_scoped: bool
    allow_market_aggregates: bool
