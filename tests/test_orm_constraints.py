"""Metadata-only checks for tenant integrity constraints (no DB required).

Mirrors migration 0006: every tenant-scoped table must declare a foreign key
account_id -> analytics.accounts.id, and users must carry the role CHECK.
"""

from sqlalchemy import CheckConstraint

from app.domain.roles import ALLOWED_ROLES
from app.infra import orm

ACCOUNT_FK_MODELS = [
    orm.AnalyticsUser,
    orm.DimVenue,
    orm.Engagement,
    orm.Finding,
    orm.Recommendation,
    orm.FactNightlyAttendance,
    orm.FactSalesByNight,
    orm.FactAttendanceByGender,
    orm.FactAttendanceDetail,
]


def test_account_id_has_fk_to_accounts() -> None:
    for model in ACCOUNT_FK_MODELS:
        column = model.__table__.c.account_id
        targets = {fk.target_fullname for fk in column.foreign_keys}
        assert "analytics.accounts.id" in targets, (
            f"{model.__name__}.account_id must reference analytics.accounts.id"
        )


def test_account_fk_uses_on_delete_restrict() -> None:
    for model in ACCOUNT_FK_MODELS:
        for fk in model.__table__.c.account_id.foreign_keys:
            if fk.target_fullname == "analytics.accounts.id":
                assert fk.ondelete == "RESTRICT", (
                    f"{model.__name__}.account_id FK must be ON DELETE RESTRICT"
                )


def test_users_role_check_constraint_matches_allowed_roles() -> None:
    checks = [
        c for c in orm.AnalyticsUser.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    role_checks = [c for c in checks if c.name == "ck_users_role_allowed"]
    assert role_checks, "users must declare ck_users_role_allowed CHECK constraint"

    sqltext = str(role_checks[0].sqltext)
    for role in ALLOWED_ROLES:
        assert f"'{role}'" in sqltext, f"role CHECK must allow '{role}'"
