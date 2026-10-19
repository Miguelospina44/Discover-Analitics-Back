"""Who can see which grain: venue (continuous) vs organizer (per event).

A colectivo/organizador sees only their event_ids (aggregated, no PII) plus
anonymous market trends. They never see the host venue's operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeVar
from uuid import UUID

T = TypeVar("T")

ActorKind = Literal["venue", "organizer"]


@dataclass(frozen=True)
class AnalyticsScope:
    """Data-access scope. Organizer without event_ids is fail-closed (no rows)."""

    account_id: UUID
    actor: ActorKind = "venue"
    event_ids: frozenset[UUID] = frozenset()

    @property
    def allows_venue_grain(self) -> bool:
        return self.actor == "venue"

    @property
    def requires_event_filter(self) -> bool:
        return self.actor == "organizer"

    def allows_event(self, event_id: UUID | None) -> bool:
        if self.actor != "organizer":
            return True
        if event_id is None:
            return False
        return event_id in self.event_ids


def venue_scope(account_id: UUID) -> AnalyticsScope:
    return AnalyticsScope(account_id=account_id, actor="venue")


def organizer_scope(account_id: UUID, event_ids: frozenset[UUID] | set[UUID]) -> AnalyticsScope:
    return AnalyticsScope(
        account_id=account_id,
        actor="organizer",
        event_ids=frozenset(event_ids),
    )


def resolve_scope(
    account_id: UUID,
    scope: AnalyticsScope | None,
) -> AnalyticsScope:
    """Fail-closed if the caller mixes another account into the scope."""
    if scope is None:
        return venue_scope(account_id)
    if scope.account_id != account_id:
        return AnalyticsScope(
            account_id=account_id,
            actor=scope.actor,
            event_ids=frozenset(),
        )
    return scope


def event_ids_clause(
    where: list[str],
    params: dict,
    scope: AnalyticsScope,
) -> bool:
    """Append event_id IN (:event_ids). Return False when the query must be empty."""
    if not scope.requires_event_filter:
        return True
    if not scope.event_ids:
        return False
    where.append("event_id IN :event_ids")
    params["event_ids"] = list(scope.event_ids)
    return True


def keep_allowed_events(rows: list[T], scope: AnalyticsScope, attr: str = "event_id") -> list[T]:
    if not scope.requires_event_filter:
        return rows
    if not scope.event_ids:
        return []
    kept: list[T] = []
    for row in rows:
        event_id = getattr(row, attr, None)
        if scope.allows_event(event_id):
            kept.append(row)
    return kept
