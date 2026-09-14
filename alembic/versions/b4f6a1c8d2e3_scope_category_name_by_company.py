"""scope category name uniqueness by company

Revision ID: b4f6a1c8d2e3
Revises: a72c41c92a5f
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b4f6a1c8d2e3"
down_revision: Union[str, None] = "a72c41c92a5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La base de production peut avoir reçu des corrections SQL avant que les
    # migrations Alembic en attente soient rejouées. Ces opérations sont donc
    # volontairement idempotentes.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_categories_user_id_nom'
                  AND conrelid = 'categories'::regclass
            ) THEN
                ALTER TABLE categories
                ADD CONSTRAINT uq_categories_user_id_nom UNIQUE (user_id, nom);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE categories "
        "DROP CONSTRAINT IF EXISTS categories_nom_key"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'categories_nom_key'
                  AND conrelid = 'categories'::regclass
            ) THEN
                ALTER TABLE categories
                ADD CONSTRAINT categories_nom_key UNIQUE (nom);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE categories "
        "DROP CONSTRAINT IF EXISTS uq_categories_user_id_nom"
    )
