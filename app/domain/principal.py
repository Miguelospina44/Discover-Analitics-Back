from dataclasses import dataclass, field
from uuid import UUID

from app.domain.access import AccessScope
from app.domain.entitlements import is_known_plan, plan_allows
from app.domain.errors import ForbiddenError
from app.domain.roles import can_write, is_known_role, is_super_admin
from app.domain.tenant import is_event_scoped, is_known_tenant_kind


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    account_id: UUID
    role: str
    email: str
    tenant_kind: str = "venue"
    plan: str = "growth"
    venue_ids: frozenset[UUID] = field(default_factory=frozenset)
    event_ids: frozenset[UUID] = field(default_factory=frozenset)
    child_account_ids: frozenset[UUID] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not is_known_role(self.role):
            raise ForbiddenError("Rol desconocido")
        if not is_known_tenant_kind(self.tenant_kind):
            raise ForbiddenError("Tipo de cuenta desconocido")
        if not is_super_admin(self.role) and not is_known_plan(self.plan):
            raise ForbiddenError("Plan desconocido")

    def require_write(self) -> None:
        if not can_write(self.role):
            raise ForbiddenError("Este rol no puede modificar estudios")

    @property
    def super_admin(self) -> bool:
        return is_super_admin(self.role)

    def has_entitlement(self, measure_or_entitlement: str) -> bool:
        if self.super_admin:
            return True
        return plan_allows(self.plan, measure_or_entitlement)

    def require_entitlement(self, measure_or_entitlement: str) -> None:
        if not self.has_entitlement(measure_or_entitlement):
            raise ForbiddenError("Tu plan no incluye esta vista")

    def resolve_account_scope(self, requested: UUID | None) -> UUID | None:
        """Return account_id to filter, or None for all accounts (super_admin only)."""
        if self.super_admin:
            return requested
        if requested is None or requested == self.account_id:
            return self.account_id
        if requested in self.child_account_ids:
            return requested
        raise ForbiddenError("No podés ver datos de otra cuenta")

    def resolve_access_scope(
        self,
        requested_account: UUID | None = None,
        requested_venue: UUID | None = None,
        requested_event: UUID | None = None,
    ) -> AccessScope:
        account_id = self.resolve_account_scope(requested_account)
        event_scoped = is_event_scoped(self.tenant_kind)

        if event_scoped:
            if not self.event_ids:
                raise ForbiddenError("Este perfil no tiene eventos asignados")
            if requested_event is not None and requested_event not in self.event_ids:
                raise ForbiddenError("No podés ver eventos ajenos")
            event_ids = frozenset({requested_event}) if requested_event else self.event_ids
        else:
            event_ids = frozenset({requested_event}) if requested_event else frozenset()

        if self.venue_ids:
            if requested_venue is not None and requested_venue not in self.venue_ids:
                raise ForbiddenError("No podés ver locales ajenos")
            venue_ids = frozenset({requested_venue}) if requested_venue else self.venue_ids
        else:
            venue_ids = frozenset({requested_venue}) if requested_venue else frozenset()

        return AccessScope(
            account_id=account_id,
            account_ids=self.child_account_ids,
            venue_ids=venue_ids,
            event_ids=event_ids,
            event_scoped=event_scoped,
            allow_market_aggregates=self.has_entitlement("market_aggregates"),
        )
