"""add subscription change requests

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_change_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("current_plan_code", sa.String(length=32), nullable=True),
        sa.Column("requested_plan_code", sa.String(length=32), nullable=False),
        sa.Column("billing_cycle", sa.String(length=16), nullable=False),
        sa.Column("quoted_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="XOF"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["current_plan_code"], ["subscription_plans.code"]),
        sa.ForeignKeyConstraint(["requested_plan_code"], ["subscription_plans.code"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("billing_cycle IN ('monthly', 'annual')", name="ck_subscription_request_cycle"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name="ck_subscription_request_status"),
    )
    op.create_index("ix_subscription_change_requests_id", "subscription_change_requests", ["id"])
    op.create_index("ix_subscription_change_requests_user_id", "subscription_change_requests", ["user_id"])
    op.create_index("ix_subscription_change_requests_status", "subscription_change_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_subscription_change_requests_status", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_user_id", table_name="subscription_change_requests")
    op.drop_index("ix_subscription_change_requests_id", table_name="subscription_change_requests")
    op.drop_table("subscription_change_requests")
