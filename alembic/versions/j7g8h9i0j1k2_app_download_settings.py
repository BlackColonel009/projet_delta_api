"""app download settings

Revision ID: j7g8h9i0j1k2
Revises: i6f7a8b9c0d1
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "j7g8h9i0j1k2"
down_revision = "i6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_download_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("download_url", sa.String(length=2048), nullable=True),
        sa.Column("version", sa.String(length=32), nullable=True),
        sa.Column("file_size_label", sa.String(length=40), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", name="uq_app_download_settings_platform"),
    )
    op.create_index(
        "ix_app_download_settings_id",
        "app_download_settings",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_app_download_settings_platform",
        "app_download_settings",
        ["platform"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_app_download_settings_platform",
        table_name="app_download_settings",
    )
    op.drop_index("ix_app_download_settings_id", table_name="app_download_settings")
    op.drop_table("app_download_settings")
