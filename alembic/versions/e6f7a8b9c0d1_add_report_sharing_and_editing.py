"""add report sharing and editing

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "report_sharing_enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "ALTER TABLE rapports ADD COLUMN IF NOT EXISTS "
        "date_modification TIMESTAMP NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE rapports DROP COLUMN IF EXISTS date_modification")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS report_sharing_enabled")
