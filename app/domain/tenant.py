from typing import Literal

TenantKind = Literal["venue", "group", "collective", "organizer"]

TENANT_KINDS: frozenset[str] = frozenset({"venue", "group", "collective", "organizer"})
EVENT_SCOPED_KINDS: frozenset[str] = frozenset({"collective", "organizer"})


def is_known_tenant_kind(kind: str) -> bool:
    return kind in TENANT_KINDS


def is_event_scoped(kind: str) -> bool:
    return kind in EVENT_SCOPED_KINDS
