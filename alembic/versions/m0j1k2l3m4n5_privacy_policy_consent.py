"""store versioned privacy policy consent

Revision ID: m0j1k2l3m4n5
Revises: l9i0j1k2l3m4
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa


revision = "m0j1k2l3m4n5"
down_revision = "l9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("privacy_policy_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("privacy_policy_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("privacy_policy_language", sa.String(length=5), nullable=True),
    )


def downgrade():
    op.drop_column("users", "privacy_policy_language")
    op.drop_column("users", "privacy_policy_accepted_at")
    op.drop_column("users", "privacy_policy_version")
