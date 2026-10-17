"""scope core inventory by enterprise

Revision ID: k2f3a4b5c6d7
Revises: j1e2f3a4b5c6
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "k2f3a4b5c6d7"
down_revision: Union[str, None] = "j1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CORE_TABLES = ("categories", "clients", "fournisseurs", "produits", "unites_produit")


def upgrade() -> None:
    for table in CORE_TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS enterprise_id INTEGER"
        )
        op.execute(
            "DO $$ BEGIN "
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_enterprise_id "
            "FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT; "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )

    for table in ("categories", "clients", "fournisseurs", "produits"):
        op.execute(
            f"UPDATE {table} AS target SET enterprise_id = e.id "
            "FROM enterprise_groups g "
            "JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE "
            "WHERE g.owner_user_id = target.user_id AND target.enterprise_id IS NULL"
        )

    op.execute(
        "UPDATE unites_produit AS unit SET enterprise_id = product.enterprise_id "
        "FROM produits product WHERE product.id = unit.produit_id "
        "AND unit.enterprise_id IS NULL"
    )

    for table in CORE_TABLES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_enterprise_id "
            f"ON {table} (enterprise_id)"
        )

    op.execute(
        "ALTER TABLE categories DROP CONSTRAINT IF EXISTS uq_categories_user_id_nom"
    )
    op.execute("DROP INDEX IF EXISTS uq_categories_user_id_nom")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_enterprise_name "
        "ON categories (enterprise_id, lower(nom)) "
        "WHERE enterprise_id IS NOT NULL"
    )

    # Un même code fabricant peut exister dans deux entreprises différentes.
    # La traçabilité Trade Care reste, elle, globalement unique.
    op.execute("DROP INDEX IF EXISTS ix_unites_produit_code_barre")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_unites_produit_code_barre "
        "ON unites_produit (code_barre)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_unites_produit_enterprise_code_barre "
        "ON unites_produit (enterprise_id, code_barre) "
        "WHERE code_barre IS NOT NULL AND enterprise_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_unites_produit_enterprise_code_barre")
    op.execute("DROP INDEX IF EXISTS ix_unites_produit_code_barre")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_unites_produit_code_barre "
        "ON unites_produit (code_barre) WHERE code_barre IS NOT NULL"
    )
    op.execute("DROP INDEX IF EXISTS uq_categories_enterprise_name")
    op.execute(
        "ALTER TABLE categories ADD CONSTRAINT uq_categories_user_id_nom UNIQUE (user_id, nom)"
    )
    for table in reversed(CORE_TABLES):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_enterprise_id")
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_enterprise_id"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS enterprise_id")
