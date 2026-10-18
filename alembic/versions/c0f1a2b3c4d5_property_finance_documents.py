"""property finance documents and maintenance"""
from alembic import op
import sqlalchemy as sa
revision="c0f1a2b3c4d5"; down_revision="b9e0f1a2b3c4"; branch_labels=None; depends_on=None


def upgrade():
    op.create_table("property_payments",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False),sa.Column("occupancy_id",sa.Integer(),sa.ForeignKey("property_occupancies.id",ondelete="CASCADE"),nullable=False),sa.Column("due_id",sa.Integer(),sa.ForeignKey("property_payment_dues.id",ondelete="SET NULL")),sa.Column("kind",sa.String(24),nullable=False),sa.Column("amount",sa.Float(),nullable=False),sa.Column("payment_method",sa.String(40),nullable=False,server_default="cash"),sa.Column("reference",sa.String(120)),sa.Column("agent_name",sa.String(160),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_property_payment_enterprise_date","property_payments",["enterprise_id","created_at"])
    op.create_table("property_inspections",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False),sa.Column("occupancy_id",sa.Integer(),sa.ForeignKey("property_occupancies.id",ondelete="CASCADE"),nullable=False),sa.Column("inspection_type",sa.String(16),nullable=False),sa.Column("notes",sa.String(2000)),sa.Column("condition_json",sa.JSON(),nullable=False),sa.Column("photos_json",sa.JSON(),nullable=False),sa.Column("signed_by_client",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("agent_name",sa.String(160),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_property_inspection_occupancy_date","property_inspections",["occupancy_id","created_at"])
    op.create_table("property_maintenance",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False),sa.Column("property_id",sa.Integer(),sa.ForeignKey("rental_properties.id",ondelete="CASCADE"),nullable=False),sa.Column("unit_id",sa.Integer(),sa.ForeignKey("property_units.id",ondelete="SET NULL")),sa.Column("title",sa.String(160),nullable=False),sa.Column("description",sa.String(1000)),sa.Column("priority",sa.String(16),nullable=False,server_default="normal"),sa.Column("status",sa.String(24),nullable=False,server_default="open"),sa.Column("estimated_cost",sa.Float(),nullable=False,server_default="0"),sa.Column("actual_cost",sa.Float(),nullable=False,server_default="0"),sa.Column("assigned_to",sa.String(160)),sa.Column("agent_name",sa.String(160),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("completed_at",sa.DateTime()))
    op.create_index("ix_property_maintenance_enterprise_status","property_maintenance",["enterprise_id","status"])


def downgrade():
    op.drop_table("property_maintenance");op.drop_table("property_inspections");op.drop_table("property_payments")
