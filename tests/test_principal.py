from uuid import uuid4

import pytest

from app.domain.errors import ForbiddenError
from app.domain.principal import Principal


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ForbiddenError):
        Principal(user_id=uuid4(), account_id=uuid4(), role="god_mode", email="a@b.c")


def test_super_admin_is_allowed() -> None:
    principal = Principal(
        user_id=uuid4(), account_id=uuid4(), role="super_admin", email="a@b.c"
    )
    assert principal.super_admin
    principal.require_write()


def test_viewer_cannot_write() -> None:
    principal = Principal(user_id=uuid4(), account_id=uuid4(), role="viewer", email="a@b.c")
    with pytest.raises(ForbiddenError):
        principal.require_write()


def test_consultant_can_write() -> None:
    principal = Principal(user_id=uuid4(), account_id=uuid4(), role="consultant", email="a@b.c")
    principal.require_write()


def test_client_cannot_scope_other_account() -> None:
    own = uuid4()
    other = uuid4()
    principal = Principal(user_id=uuid4(), account_id=own, role="admin", email="a@b.c")
    with pytest.raises(ForbiddenError):
        principal.resolve_account_scope(other)


def test_super_admin_global_scope() -> None:
    principal = Principal(
        user_id=uuid4(), account_id=uuid4(), role="super_admin", email="a@b.c"
    )
    assert principal.resolve_account_scope(None) is None
