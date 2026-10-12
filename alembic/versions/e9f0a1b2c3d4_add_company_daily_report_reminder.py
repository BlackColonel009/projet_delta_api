"""add company daily report reminder

Revision ID: e9f0a1b2c3d4
Revises: d7e8f9a0b1c2
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e9f0a1b2c3d4"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_reminder_enabled BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_reminder_hour INTEGER NOT NULL DEFAULT 18"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_reminder_minute INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_reminder_revision INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "daily_report_reminder_updated_at TIMESTAMP NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_reminder_updated_at"
    )
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_reminder_revision"
    )
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_reminder_minute"
    )
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_reminder_hour"
    )
    op.execute(
        "ALTER TABLE users DROP COLUMN IF EXISTS daily_report_reminder_enabled"
    )
