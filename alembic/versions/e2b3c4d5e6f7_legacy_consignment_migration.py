"""legacy consignment assisted migration"""
from alembic import op
import sqlalchemy as sa
revision="e2b3c4d5e6f7";down_revision="d1a2b3c4d5e6";branch_labels=None;depends_on=None


def upgrade():
    op.create_table("legacy_migration_batches",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("group_id",sa.Integer(),sa.ForeignKey("enterprise_groups.id",ondelete="CASCADE"),nullable=False),sa.Column("source_enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id"),nullable=False),sa.Column("target_enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id"),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="running"),sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),sa.Column("report_json",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("completed_at",sa.DateTime()))
    op.create_index("ix_legacy_migration_group_date","legacy_migration_batches",["group_id","created_at"])
    op.create_table("legacy_client_mappings",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("source_client_id",sa.Integer(),sa.ForeignKey("clients.id"),nullable=False),sa.Column("target_client_id",sa.Integer(),sa.ForeignKey("clients.id"),nullable=False),sa.Column("target_enterprise_id",sa.Integer(),sa.ForeignKey("enterprises.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("source_client_id","target_enterprise_id",name="uq_legacy_client_target"))
    op.create_table("legacy_migration_items",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("batch_id",sa.Integer(),sa.ForeignKey("legacy_migration_batches.id",ondelete="CASCADE"),nullable=False),sa.Column("source_depot_id",sa.Integer(),sa.ForeignKey("depots.id"),nullable=False),sa.Column("target_laundry_order_id",sa.Integer(),sa.ForeignKey("laundry_orders.id")),sa.Column("target_client_id",sa.Integer(),sa.ForeignKey("clients.id")),sa.Column("status",sa.String(24),nullable=False),sa.Column("reason",sa.String(500)),sa.Column("snapshot_json",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("source_depot_id",name="uq_legacy_migration_source_depot"))
    op.create_index("ix_legacy_migration_item_batch","legacy_migration_items",["batch_id"])


def downgrade():op.drop_table("legacy_migration_items");op.drop_table("legacy_client_mappings");op.drop_table("legacy_migration_batches")
