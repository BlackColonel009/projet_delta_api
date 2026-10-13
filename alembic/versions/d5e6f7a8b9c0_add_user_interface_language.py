"""add user interface language

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "interface_language VARCHAR(5) NOT NULL DEFAULT 'fr'"
    )
    op.execute(
        "ALTER TABLE sub_users ADD COLUMN IF NOT EXISTS "
        "interface_language VARCHAR(5) NOT NULL DEFAULT 'fr'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sub_users DROP COLUMN IF EXISTS interface_language")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS interface_language")
