"""platform contact links

Revision ID: k8h9i0j1k2l3
Revises: j7g8h9i0j1k2
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "k8h9i0j1k2l3"
down_revision = "j7g8h9i0j1k2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_contact_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("icon_key", sa.String(length=24), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_contact_links_id",
        "platform_contact_links",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_platform_contact_links_public_order",
        "platform_contact_links",
        ["is_visible", "sort_order", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_platform_contact_links_public_order",
        table_name="platform_contact_links",
    )
    op.drop_index("ix_platform_contact_links_id", table_name="platform_contact_links")
    op.drop_table("platform_contact_links")
