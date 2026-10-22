"""offline report idempotency

Revision ID: i6f7a8b9c0d1
Revises: h5e6f7a8b9c0
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "i6f7a8b9c0d1"
down_revision = "h5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rapports",
        sa.Column("client_reference", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_rapports_enterprise_client_reference",
        "rapports",
        ["enterprise_id", "client_reference"],
    )


def downgrade():
    op.drop_constraint(
        "uq_rapports_enterprise_client_reference",
        "rapports",
        type_="unique",
    )
    op.drop_column("rapports", "client_reference")
