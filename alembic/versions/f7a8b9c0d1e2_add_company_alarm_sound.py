"""add company alarm sound

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_alarm_sound VARCHAR(32) NOT NULL DEFAULT 'signature'"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_alarm_sound_revision INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS "
        "daily_report_alarm_sound_revision"
    )
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_alarm_sound"
    )
