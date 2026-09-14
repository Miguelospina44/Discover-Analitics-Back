"""account_id foreign keys to accounts and role CHECK on users

Enforces tenant integrity at the database level: every account_id must point to
a real analytics.accounts row, and users.role must be one of the allowed roles.
This is the backbone for all future per-account tables (audience, events,
forecasts): tenant isolation becomes a database invariant, not only app logic.

Revision ID: 0006_account_fks_role_check
Revises: 0005_attendance_detail
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_account_fks_role_check"
down_revision: Union[str, Sequence[str], None] = "0005_attendance_detail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table in `analytics` that carries a tenant `account_id` column.
ACCOUNT_FK_TABLES: tuple[str, ...] = (
    "users",
    "dim_venues",
    "engagements",
    "findings",
    "recommendations",
    "fact_nightly_attendance",
    "fact_sales_by_night",
    "fact_attendance_by_gender",
    "fact_attendance_detail",
)

# Keep in sync with app.domain.roles.ALLOWED_ROLES.
ALLOWED_ROLES: tuple[str, ...] = ("admin", "consultant", "viewer", "super_admin")


def _fk_name(table: str) -> str:
    return f"fk_{table}_account"


def upgrade() -> None:
    for table in ACCOUNT_FK_TABLES:
        op.create_foreign_key(
            _fk_name(table),
            source_table=table,
            referent_table="accounts",
            local_cols=["account_id"],
            remote_cols=["id"],
            source_schema="analytics",
            referent_schema="analytics",
            ondelete="RESTRICT",
        )

    roles_csv = ", ".join(f"'{role}'" for role in ALLOWED_ROLES)
    op.create_check_constraint(
        "ck_users_role_allowed",
        "users",
        f"role IN ({roles_csv})",
        schema="analytics",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_allowed", "users", schema="analytics", type_="check")
    for table in reversed(ACCOUNT_FK_TABLES):
        op.drop_constraint(_fk_name(table), table, schema="analytics", type_="foreignkey")
