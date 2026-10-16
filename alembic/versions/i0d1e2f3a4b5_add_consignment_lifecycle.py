"""add controlled consignment lifecycle metadata

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "i0d1e2f3a4b5"
down_revision: Union[str, None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS date_stockage TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS date_pret_retrait TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS date_annulation TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS motif_annulation VARCHAR"
    )
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS statut_modifie_le TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE depots ADD COLUMN IF NOT EXISTS statut_modifie_par INTEGER"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE depots ADD CONSTRAINT fk_depots_statut_modifie_par_users "
        "FOREIGN KEY (statut_modifie_par) REFERENCES users(id) ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_depots_user_statut "
        "ON depots (user_id, statut)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_depots_user_statut")
    op.execute(
        "ALTER TABLE depots DROP CONSTRAINT IF EXISTS "
        "fk_depots_statut_modifie_par_users"
    )
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS statut_modifie_par")
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS statut_modifie_le")
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS motif_annulation")
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS date_annulation")
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS date_pret_retrait")
    op.execute("ALTER TABLE depots DROP COLUMN IF EXISTS date_stockage")

