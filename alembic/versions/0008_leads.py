"""leads (public lead-capture) table

Lead-capture es un flujo PÚBLICO y separado de la analítica anónima: un
visitante entrega datos de contacto (nombre, teléfono, fecha de nacimiento,
correo) antes de ser redirigido a Discover. A diferencia del resto del schema
`analytics`, esta tabla contiene PII y NO lleva account_id/tenant FK: son leads
públicos, no pertenecen a una cuenta.

NOTA DE PRIVACIDAD (producción): antes de usar esto con datos reales hay que
añadir consentimiento explícito, política de retención y manejo de datos
personales (habeas data). Aquí es solo un flujo de prueba con datos ficticios.

Revision ID: 0008_leads
Revises: 0007_events
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_leads"
down_revision: Union[str, Sequence[str], None] = "0007_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="analytics",
    )
    op.create_index(
        "ix_leads_created_at",
        "leads",
        ["created_at"],
        schema="analytics",
    )
    op.create_index(
        "ix_leads_email",
        "leads",
        ["email"],
        schema="analytics",
    )


def downgrade() -> None:
    op.drop_index("ix_leads_email", table_name="leads", schema="analytics")
    op.drop_index("ix_leads_created_at", table_name="leads", schema="analytics")
    op.drop_table("leads", schema="analytics")
