"""add legacy enterprise write guards

Revision ID: l3a4b5c6d7e8
Revises: k2f3a4b5c6d7
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "l3a4b5c6d7e8"
down_revision: Union[str, None] = "k2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNER_TABLES = ("categories", "clients", "fournisseurs", "produits")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION tradecare_assign_enterprise_from_owner()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.enterprise_id IS NULL AND NEW.user_id IS NOT NULL THEN
                SELECT e.id INTO NEW.enterprise_id
                FROM enterprise_groups g
                JOIN enterprises e
                  ON e.group_id = g.id
                 AND e.is_primary IS TRUE
                 AND e.status = 'active'
                WHERE g.owner_user_id = NEW.user_id
                LIMIT 1;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in OWNER_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_assign_enterprise "
            f"BEFORE INSERT OR UPDATE OF user_id, enterprise_id ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION tradecare_assign_enterprise_from_owner()"
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION tradecare_assign_unit_enterprise_from_product()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.enterprise_id IS NULL AND NEW.produit_id IS NOT NULL THEN
                SELECT p.enterprise_id INTO NEW.enterprise_id
                FROM produits p
                WHERE p.id = NEW.produit_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_unites_produit_assign_enterprise "
        "ON unites_produit"
    )
    op.execute(
        "CREATE TRIGGER trg_unites_produit_assign_enterprise "
        "BEFORE INSERT OR UPDATE OF produit_id, enterprise_id ON unites_produit "
        "FOR EACH ROW EXECUTE FUNCTION "
        "tradecare_assign_unit_enterprise_from_product()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_unites_produit_assign_enterprise "
        "ON unites_produit"
    )
    for table in OWNER_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}"
        )
    op.execute(
        "DROP FUNCTION IF EXISTS tradecare_assign_unit_enterprise_from_product()"
    )
    op.execute("DROP FUNCTION IF EXISTS tradecare_assign_enterprise_from_owner()")
