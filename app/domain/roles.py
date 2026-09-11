ALLOWED_ROLES = frozenset({"admin", "consultant", "viewer", "super_admin"})
WRITE_ROLES = frozenset({"admin", "consultant", "super_admin"})


def can_write(role: str) -> bool:
    return role in WRITE_ROLES


def is_known_role(role: str) -> bool:
    return role in ALLOWED_ROLES


def is_super_admin(role: str) -> bool:
    return role == "super_admin"
