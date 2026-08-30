"""analytics schema and consulting core tables

Revision ID: 0001_analytics_core
Revises:
Create Date: 2026-08-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001_analytics_core"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    op.execute(
        """
        CREATE TABLE analytics.users (
            id UUID PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(32) NOT NULL,
            account_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE analytics.engagements (
            id UUID PRIMARY KEY,
            account_id UUID NOT NULL,
            title VARCHAR(200) NOT NULL,
            client_name VARCHAR(200) NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            scope TEXT NOT NULL,
            objectives TEXT NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX ix_analytics_engagements_account_id ON analytics.engagements (account_id)")
    op.execute(
        """
        CREATE TABLE analytics.findings (
            id UUID PRIMARY KEY,
            account_id UUID NOT NULL,
            engagement_id UUID NOT NULL REFERENCES analytics.engagements (id),
            title VARCHAR(200) NOT NULL,
            evidence TEXT NOT NULL,
            visual_id VARCHAR(80),
            impact VARCHAR(32) NOT NULL,
            confidence VARCHAR(32) NOT NULL,
            review_status VARCHAR(32) NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX ix_analytics_findings_account_id ON analytics.findings (account_id)")
    op.execute(
        """
        CREATE TABLE analytics.recommendations (
            id UUID PRIMARY KEY,
            account_id UUID NOT NULL,
            engagement_id UUID NOT NULL REFERENCES analytics.engagements (id),
            finding_id UUID REFERENCES analytics.findings (id),
            action TEXT NOT NULL,
            expected_impact TEXT NOT NULL,
            effort VARCHAR(32) NOT NULL,
            priority VARCHAR(32) NOT NULL,
            owner VARCHAR(120) NOT NULL,
            due_date DATE,
            status VARCHAR(32) NOT NULL DEFAULT 'pending_decision',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_analytics_recommendations_account_id ON analytics.recommendations (account_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analytics.recommendations")
    op.execute("DROP TABLE IF EXISTS analytics.findings")
    op.execute("DROP TABLE IF EXISTS analytics.engagements")
    op.execute("DROP TABLE IF EXISTS analytics.users")
    op.execute("DROP SCHEMA IF EXISTS analytics")
