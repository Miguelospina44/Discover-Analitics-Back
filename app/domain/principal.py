from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import ForbiddenError
from app.domain.roles import can_write, is_known_role, is_super_admin


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    account_id: UUID
    role: str
    email: str

    def __post_init__(self) -> None:
        if not is_known_role(self.role):
            raise ForbiddenError("Rol desconocido")

    def require_write(self) -> None:
        if not can_write(self.role):
            raise ForbiddenError("Este rol no puede modificar estudios")

    @property
    def super_admin(self) -> bool:
        return is_super_admin(self.role)

    def resolve_account_scope(self, requested: UUID | None) -> UUID | None:
        """Return account_id to filter, or None for all accounts (super_admin only)."""
        if self.super_admin:
            return requested  # None = global
        if requested is not None and requested != self.account_id:
            raise ForbiddenError("No podés ver datos de otra cuenta")
        return self.account_id
