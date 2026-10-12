"""index notifications polling

Revision ID: c6d7e8f9a0b1
Revises: b4f6a1c8d2e3
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b4f6a1c8d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS garde la migration sûre si l'index a déjà été ajouté
    # manuellement sur une base de production.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_parent_unread_created "
        "ON notifications (parent_user_id, is_read, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notifications_parent_unread_created")
