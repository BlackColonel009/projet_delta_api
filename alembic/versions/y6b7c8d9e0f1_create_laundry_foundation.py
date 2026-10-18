"""create laundry foundation

Revision ID: y6b7c8d9e0f1
Revises: x5a6b7c8d9e0
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "y6b7c8d9e0f1"
down_revision = "x5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "laundry_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("pricing_mode", sa.String(24), nullable=False, server_default="per_item"),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("turnaround_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("enterprise_id", "name", name="uq_laundry_services_enterprise_name"),
    )
    op.create_index("ix_laundry_services_enterprise_active", "laundry_services", ["enterprise_id", "is_active"])
    op.create_table(
        "laundry_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("order_number", sa.String(40), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("ready_at", sa.DateTime()),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.Column("notes", sa.String(1000)),
        sa.Column("subtotal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("discount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_by_name", sa.String(160), nullable=False),
        sa.Column("created_by_role", sa.String(60)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("enterprise_id", "order_number", name="uq_laundry_orders_number"),
    )
    op.create_index("ix_laundry_orders_enterprise_status", "laundry_orders", ["enterprise_id", "status"])
    op.create_index("ix_laundry_orders_enterprise_received", "laundry_orders", ["enterprise_id", "received_at"])
    op.create_index("ix_laundry_orders_enterprise_due", "laundry_orders", ["enterprise_id", "due_at"])
    op.create_table(
        "laundry_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("laundry_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("laundry_services.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_snapshot", sa.Float(), nullable=False),
        sa.Column("line_total", sa.Float(), nullable=False),
        sa.Column("condition_notes", sa.String(500)),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_laundry_items_order", "laundry_items", ["order_id"])
    op.create_table(
        "laundry_order_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("laundry_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("agent_name", sa.String(160), nullable=False),
        sa.Column("agent_role", sa.String(60)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_laundry_events_order_date", "laundry_order_events", ["order_id", "created_at"])


def downgrade():
    op.drop_table("laundry_order_events")
    op.drop_table("laundry_items")
    op.drop_table("laundry_orders")
    op.drop_table("laundry_services")
