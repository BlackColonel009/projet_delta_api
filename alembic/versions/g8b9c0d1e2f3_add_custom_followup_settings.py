"""add custom payment and customer follow-up settings

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE client_followup ADD COLUMN IF NOT EXISTS "
        "payment_reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
        "followup_enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
        "followup_thank_you_delay_days INTEGER NOT NULL DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
        "followup_recommendations_enabled BOOLEAN NOT NULL DEFAULT TRUE"
    )
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
        "followup_first_recommendation_delay_days INTEGER NOT NULL DEFAULT 10"
    )
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS "
        "followup_recommendation_interval_days INTEGER NOT NULL DEFAULT 14"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE clients DROP COLUMN IF EXISTS "
        "followup_recommendation_interval_days"
    )
    op.execute(
        "ALTER TABLE clients DROP COLUMN IF EXISTS "
        "followup_first_recommendation_delay_days"
    )
    op.execute(
        "ALTER TABLE clients DROP COLUMN IF EXISTS "
        "followup_recommendations_enabled"
    )
    op.execute(
        "ALTER TABLE clients DROP COLUMN IF EXISTS "
        "followup_thank_you_delay_days"
    )
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS followup_enabled")
    op.execute(
        "ALTER TABLE client_followup DROP COLUMN IF EXISTS "
        "payment_reminder_enabled"
    )
