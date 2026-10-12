"""link units to purchase orders

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE unites_produit ADD COLUMN IF NOT EXISTS "
        "commande_achat_id INTEGER NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unites_produit_commande_achat_id "
        "ON unites_produit (commande_achat_id)"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE unites_produit ADD CONSTRAINT "
        "fk_unites_produit_commande_achat "
        "FOREIGN KEY (commande_achat_id) REFERENCES commandes_achats(id) "
        "ON DELETE SET NULL; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE unites_produit DROP CONSTRAINT IF EXISTS "
        "fk_unites_produit_commande_achat"
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_unites_produit_commande_achat_id"
    )
    op.execute(
        "ALTER TABLE unites_produit DROP COLUMN IF EXISTS commande_achat_id"
    )
