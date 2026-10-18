"""vehicle rental finance"""
from alembic import op
import sqlalchemy as sa

revision = "a8d9e0f1a2b3"
down_revision = "z7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vehicle_rental_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False, server_default="cash"),
        sa.Column("reference", sa.String(120)), sa.Column("agent_name", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_vehicle_rental_payment_enterprise_date", "vehicle_rental_payments", ["enterprise_id", "created_at"])
    op.create_table("vehicle_rental_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("label", sa.String(160), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False), sa.Column("notes", sa.String(500)),
        sa.Column("agent_name", sa.String(160), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_vehicle_rental_charge_reservation", "vehicle_rental_charges", ["reservation_id"])


def downgrade():
    op.drop_table("vehicle_rental_charges")
    op.drop_table("vehicle_rental_payments")
