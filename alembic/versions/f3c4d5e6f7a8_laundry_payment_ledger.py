"""add laundry payment ledger

Revision ID: f3c4d5e6f7a8
Revises: e2b3c4d5e6f7
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "f3c4d5e6f7a8"
down_revision = "e2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "laundry_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "enterprise_id",
            sa.Integer(),
            sa.ForeignKey("enterprises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("laundry_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False, server_default="cash"),
        sa.Column("agent_name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_laundry_payments_enterprise_date",
        "laundry_payments",
        ["enterprise_id", "created_at"],
    )
    # Preserve already collected amounts. Future payments receive their exact date.
    op.execute(
        """
        INSERT INTO laundry_payments
            (enterprise_id, order_id, amount, payment_method, agent_name, created_at)
        SELECT enterprise_id, id, paid_amount, 'legacy', created_by_name,
               COALESCE(updated_at, created_at)
        FROM laundry_orders
        WHERE paid_amount > 0
        """
    )


def downgrade():
    op.drop_index(
        "ix_laundry_payments_enterprise_date",
        table_name="laundry_payments",
    )
    op.drop_table("laundry_payments")
