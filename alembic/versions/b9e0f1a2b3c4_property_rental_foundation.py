"""property rental foundation"""
from alembic import op
import sqlalchemy as sa
revision="b9e0f1a2b3c4"; down_revision="a8d9e0f1a2b3"; branch_labels=None; depends_on=None


def upgrade():
    op.create_table("rental_properties",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False), sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("name",sa.String(160),nullable=False), sa.Column("property_type",sa.String(40),nullable=False), sa.Column("address",sa.String(500),nullable=False), sa.Column("description",sa.String(1000)), sa.Column("photos_json",sa.JSON(),nullable=False), sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()), sa.Column("created_at",sa.DateTime(),nullable=False), sa.Column("updated_at",sa.DateTime(),nullable=False))
    op.create_index("ix_rental_property_enterprise_active","rental_properties",["enterprise_id","is_active"])
    op.create_table("property_units",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False), sa.Column("property_id",sa.Integer(),sa.ForeignKey("rental_properties.id",ondelete="CASCADE"),nullable=False),
        sa.Column("code",sa.String(80),nullable=False), sa.Column("name",sa.String(160),nullable=False), sa.Column("unit_type",sa.String(40),nullable=False), sa.Column("rental_mode",sa.String(24),nullable=False,server_default="long_term"), sa.Column("capacity",sa.Integer(),nullable=False,server_default="1"), sa.Column("monthly_rate",sa.Float()), sa.Column("nightly_rate",sa.Float()), sa.Column("deposit_amount",sa.Float(),nullable=False,server_default="0"), sa.Column("status",sa.String(32),nullable=False,server_default="available"), sa.Column("amenities_json",sa.JSON(),nullable=False), sa.Column("created_at",sa.DateTime(),nullable=False), sa.Column("updated_at",sa.DateTime(),nullable=False), sa.UniqueConstraint("property_id","code",name="uq_property_unit_code"))
    op.create_index("ix_property_unit_enterprise_status","property_units",["enterprise_id","status"])
    op.create_table("property_occupancies",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False), sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False), sa.Column("unit_id",sa.Integer(),sa.ForeignKey("property_units.id"),nullable=False), sa.Column("client_id",sa.Integer(),sa.ForeignKey("clients.id"),nullable=False),
        sa.Column("contract_number",sa.String(40),nullable=False), sa.Column("occupancy_type",sa.String(24),nullable=False), sa.Column("status",sa.String(32),nullable=False,server_default="reserved"), sa.Column("start_at",sa.DateTime(),nullable=False), sa.Column("end_at",sa.DateTime()), sa.Column("rate_snapshot",sa.Float(),nullable=False), sa.Column("deposit_snapshot",sa.Float(),nullable=False,server_default="0"), sa.Column("total_amount",sa.Float(),nullable=False,server_default="0"), sa.Column("paid_amount",sa.Float(),nullable=False,server_default="0"), sa.Column("deposit_held",sa.Float(),nullable=False,server_default="0"), sa.Column("billing_day",sa.Integer()), sa.Column("created_by_name",sa.String(160),nullable=False), sa.Column("created_at",sa.DateTime(),nullable=False), sa.Column("updated_at",sa.DateTime(),nullable=False), sa.UniqueConstraint("enterprise_id","contract_number",name="uq_property_contract_number"))
    op.create_index("ix_property_occupancy_unit_dates","property_occupancies",["unit_id","start_at","end_at"]); op.create_index("ix_property_occupancy_enterprise_status","property_occupancies",["enterprise_id","status"])
    op.create_table("property_payment_dues",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False), sa.Column("occupancy_id",sa.Integer(),sa.ForeignKey("property_occupancies.id",ondelete="CASCADE"),nullable=False), sa.Column("due_date",sa.DateTime(),nullable=False), sa.Column("amount",sa.Float(),nullable=False), sa.Column("paid_amount",sa.Float(),nullable=False,server_default="0"), sa.Column("status",sa.String(24),nullable=False,server_default="pending"), sa.Column("created_at",sa.DateTime(),nullable=False), sa.UniqueConstraint("occupancy_id","due_date",name="uq_property_due_date"))
    op.create_index("ix_property_due_enterprise_status_date","property_payment_dues",["enterprise_id","status","due_date"])


def downgrade():
    op.drop_table("property_payment_dues"); op.drop_table("property_occupancies"); op.drop_table("property_units"); op.drop_table("rental_properties")
