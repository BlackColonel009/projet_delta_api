"""invoice share quotas

Revision ID: l9i0j1k2l3m4
Revises: k8h9i0j1k2l3
Create Date: 2026-10-30
"""

from alembic import op
import sqlalchemy as sa


revision = "l9i0j1k2l3m4"
down_revision = "k8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subscription_plans",
        sa.Column("max_invoice_shares_per_month", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE subscription_plans "
        "SET max_invoice_shares_per_month = CASE "
        "WHEN code = 'bronze_free' THEN 5 "
        "WHEN code = 'bronze_classic' THEN 50 "
        "WHEN code = 'gold' THEN 250 "
        "ELSE NULL END"
    )
    op.create_table(
        "invoice_share_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("enterprise_id", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"]),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["factures.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoice_share_events_id",
        "invoice_share_events",
        ["id"],
    )
    op.create_index(
        "ix_invoice_share_owner_created",
        "invoice_share_events",
        ["owner_user_id", "created_at"],
    )


def downgrade():
    op.drop_index(
        "ix_invoice_share_owner_created",
        table_name="invoice_share_events",
    )
    op.drop_index(
        "ix_invoice_share_events_id",
        table_name="invoice_share_events",
    )
    op.drop_table("invoice_share_events")
    op.drop_column("subscription_plans", "max_invoice_shares_per_month")
