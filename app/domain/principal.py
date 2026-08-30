from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import ForbiddenError
from app.domain.roles import can_write, is_known_role


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
