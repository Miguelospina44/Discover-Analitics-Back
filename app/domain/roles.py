ALLOWED_ROLES = frozenset({"admin", "consultant", "viewer"})
WRITE_ROLES = frozenset({"admin", "consultant"})


def can_write(role: str) -> bool:
    return role in WRITE_ROLES


def is_known_role(role: str) -> bool:
    return role in ALLOWED_ROLES
