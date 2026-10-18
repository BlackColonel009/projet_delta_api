"""create vehicle rental foundation"""
from alembic import op
import sqlalchemy as sa

revision = "z7c8d9e0f1a2"
down_revision = "y6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rental_vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("category", sa.String(80), nullable=False),
        sa.Column("brand", sa.String(80), nullable=False), sa.Column("model", sa.String(80), nullable=False),
        sa.Column("year", sa.Integer()), sa.Column("registration_number", sa.String(60), nullable=False),
        sa.Column("vin", sa.String(80)), sa.Column("color", sa.String(50)),
        sa.Column("mileage", sa.Float(), nullable=False, server_default="0"), sa.Column("fuel_level", sa.Float()),
        sa.Column("daily_rate", sa.Float(), nullable=False, server_default="0"), sa.Column("hourly_rate", sa.Float()),
        sa.Column("weekly_rate", sa.Float()), sa.Column("deposit_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="available"),
        sa.Column("documents_json", sa.JSON(), nullable=False), sa.Column("photos_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("enterprise_id", "registration_number", name="uq_rental_vehicle_registration"))
    op.create_index("ix_rental_vehicle_enterprise_status", "rental_vehicles", ["enterprise_id", "status"])
    op.create_table("vehicle_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("rental_vehicles.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("reservation_number", sa.String(40), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="reserved"),
        sa.Column("start_at", sa.DateTime(), nullable=False), sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("rate_snapshot", sa.Float(), nullable=False), sa.Column("deposit_snapshot", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_total", sa.Float(), nullable=False, server_default="0"), sa.Column("paid_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deposit_paid", sa.Float(), nullable=False, server_default="0"),
        sa.Column("start_mileage", sa.Float()), sa.Column("end_mileage", sa.Float()),
        sa.Column("start_fuel_level", sa.Float()), sa.Column("end_fuel_level", sa.Float()),
        sa.Column("departure_notes", sa.String(1000)), sa.Column("return_notes", sa.String(1000)),
        sa.Column("inspection_json", sa.JSON(), nullable=False),
        sa.Column("created_by_name", sa.String(160), nullable=False), sa.Column("created_by_role", sa.String(60)),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("enterprise_id", "reservation_number", name="uq_vehicle_reservation_number"))
    op.create_index("ix_vehicle_reservation_vehicle_dates", "vehicle_reservations", ["vehicle_id", "start_at", "end_at"])
    op.create_index("ix_vehicle_reservation_enterprise_status", "vehicle_reservations", ["enterprise_id", "status"])
    op.create_table("vehicle_rental_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(32)), sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("note", sa.String(500)), sa.Column("agent_name", sa.String(160), nullable=False),
        sa.Column("agent_role", sa.String(60)), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_vehicle_rental_events_reservation_date", "vehicle_rental_events", ["reservation_id", "created_at"])


def downgrade():
    op.drop_table("vehicle_rental_events")
    op.drop_table("vehicle_reservations")
    op.drop_table("rental_vehicles")
