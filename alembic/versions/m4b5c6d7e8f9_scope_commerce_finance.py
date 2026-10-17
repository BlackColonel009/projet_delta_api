"""scope commerce and finance by enterprise

Revision ID: m4b5c6d7e8f9
Revises: l3a4b5c6d7e8
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "m4b5c6d7e8f9"
down_revision: Union[str, None] = "l3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (
    "commandes_ventes",
    "lignes_commandes_ventes",
    "commandes_achats",
    "lignes_commandes_achats",
    "factures",
    "lignes_facture",
    "paiements",
    "depenses",
    "client_produits",
    "client_followup",
)


def _add_enterprise_column(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS enterprise_id INTEGER")
    op.execute(
        "DO $$ BEGIN "
        f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_enterprise_id "
        "FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_{table}_enterprise_id "
        f"ON {table} (enterprise_id)"
    )


def _owner_backfill(table: str) -> None:
    op.execute(
        f"UPDATE {table} AS target SET enterprise_id = e.id "
        "FROM enterprise_groups g "
        "JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE "
        "WHERE g.owner_user_id = target.user_id AND target.enterprise_id IS NULL"
    )


def _parent_backfill(table: str, parent_table: str, foreign_key: str) -> None:
    op.execute(
        f"UPDATE {table} AS child SET enterprise_id = parent.enterprise_id "
        f"FROM {parent_table} AS parent "
        f"WHERE parent.id = child.{foreign_key} AND child.enterprise_id IS NULL"
    )


def upgrade() -> None:
    for table in TABLES:
        _add_enterprise_column(table)

    _owner_backfill("commandes_ventes")
    _owner_backfill("commandes_achats")
    _owner_backfill("depenses")
    _parent_backfill(
        "lignes_commandes_ventes", "commandes_ventes", "commande_id"
    )
    _parent_backfill(
        "lignes_commandes_achats", "commandes_achats", "commande_id"
    )

    # Les factures liées héritent en priorité de leur commande. Les factures
    # manuelles utilisent ensuite l'entreprise principale du propriétaire.
    op.execute(
        "UPDATE factures f SET enterprise_id = cv.enterprise_id "
        "FROM commandes_ventes cv WHERE cv.id = f.commande_id "
        "AND f.enterprise_id IS NULL"
    )
    op.execute(
        "UPDATE factures f SET enterprise_id = ca.enterprise_id "
        "FROM commandes_achats ca WHERE ca.id = f.commande_achat_id "
        "AND f.enterprise_id IS NULL"
    )
    _owner_backfill("factures")
    op.execute(
        "UPDATE factures f SET enterprise_id = c.enterprise_id "
        "FROM clients c WHERE c.id = f.client_id AND f.enterprise_id IS NULL"
    )
    op.execute(
        "UPDATE factures f SET enterprise_id = s.enterprise_id "
        "FROM fournisseurs s WHERE s.id = f.fournisseur_id "
        "AND f.enterprise_id IS NULL"
    )
    _parent_backfill("lignes_facture", "factures", "facture_id")
    _parent_backfill("paiements", "factures", "facture_id")
    _parent_backfill("client_produits", "commandes_ventes", "commande_id")
    _parent_backfill("client_followup", "commandes_ventes", "commande_id")

    # Compatibilité pendant le déploiement progressif de l'API.
    for table in ("commandes_ventes", "commandes_achats", "depenses"):
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
        CREATE OR REPLACE FUNCTION tradecare_assign_commerce_enterprise()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.enterprise_id IS NOT NULL THEN
                RETURN NEW;
            END IF;
            IF TG_TABLE_NAME = 'lignes_commandes_ventes' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM commandes_ventes WHERE id = NEW.commande_id;
            ELSIF TG_TABLE_NAME = 'lignes_commandes_achats' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM commandes_achats WHERE id = NEW.commande_id;
            ELSIF TG_TABLE_NAME = 'factures' THEN
                IF NEW.commande_id IS NOT NULL THEN
                    SELECT enterprise_id INTO NEW.enterprise_id FROM commandes_ventes WHERE id = NEW.commande_id;
                ELSIF NEW.commande_achat_id IS NOT NULL THEN
                    SELECT enterprise_id INTO NEW.enterprise_id FROM commandes_achats WHERE id = NEW.commande_achat_id;
                END IF;
                IF NEW.enterprise_id IS NULL AND NEW.user_id IS NOT NULL THEN
                    SELECT e.id INTO NEW.enterprise_id
                    FROM enterprise_groups g JOIN enterprises e
                      ON e.group_id = g.id AND e.is_primary IS TRUE
                    WHERE g.owner_user_id = NEW.user_id LIMIT 1;
                END IF;
                IF NEW.enterprise_id IS NULL AND NEW.client_id IS NOT NULL THEN
                    SELECT enterprise_id INTO NEW.enterprise_id FROM clients WHERE id = NEW.client_id;
                ELSIF NEW.enterprise_id IS NULL AND NEW.fournisseur_id IS NOT NULL THEN
                    SELECT enterprise_id INTO NEW.enterprise_id FROM fournisseurs WHERE id = NEW.fournisseur_id;
                END IF;
            ELSIF TG_TABLE_NAME = 'lignes_facture' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM factures WHERE id = NEW.facture_id;
            ELSIF TG_TABLE_NAME = 'paiements' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM factures WHERE id = NEW.facture_id;
            ELSIF TG_TABLE_NAME IN ('client_produits', 'client_followup') THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM commandes_ventes WHERE id = NEW.commande_id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    trigger_specs = {
        "lignes_commandes_ventes": "commande_id, enterprise_id",
        "lignes_commandes_achats": "commande_id, enterprise_id",
        "factures": "commande_id, commande_achat_id, client_id, fournisseur_id, user_id, enterprise_id",
        "lignes_facture": "facture_id, enterprise_id",
        "paiements": "facture_id, enterprise_id",
        "client_produits": "commande_id, enterprise_id",
        "client_followup": "commande_id, enterprise_id",
    }
    for table, columns in trigger_specs.items():
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_assign_enterprise "
            f"BEFORE INSERT OR UPDATE OF {columns} ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION tradecare_assign_commerce_enterprise()"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}"
        )
    op.execute("DROP FUNCTION IF EXISTS tradecare_assign_commerce_enterprise()")
    for table in reversed(TABLES):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_enterprise_id")
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_enterprise_id"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS enterprise_id")
