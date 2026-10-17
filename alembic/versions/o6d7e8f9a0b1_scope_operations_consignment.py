"""scope operations and consignment by enterprise

Revision ID: o6d7e8f9a0b1
Revises: n5c6d7e8f9a0
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op


revision: str = "o6d7e8f9a0b1"
down_revision: Union[str, None] = "n5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "interventions", "intervention_produits", "historiques_interventions",
    "rapports", "notifications", "historiques", "galerie_photos",
    "depot_services", "depot_tarifs", "depots", "depot_tarif_item",
    "factures_depot",
)


def _add(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS enterprise_id INTEGER")
    op.execute(
        "DO $$ BEGIN "
        f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_enterprise_id "
        "FOREIGN KEY (enterprise_id) REFERENCES enterprises(id) ON DELETE RESTRICT; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_{table}_enterprise_id ON {table} (enterprise_id)"
    )


def _owner(table: str, owner_column: str = "user_id") -> None:
    op.execute(
        f"UPDATE {table} target SET enterprise_id = e.id "
        "FROM enterprise_groups g JOIN enterprises e "
        "ON e.group_id = g.id AND e.is_primary IS TRUE "
        f"WHERE g.owner_user_id = target.{owner_column} "
        "AND target.enterprise_id IS NULL"
    )


def _parent(table: str, parent: str, fk: str) -> None:
    op.execute(
        f"UPDATE {table} child SET enterprise_id = parent.enterprise_id "
        f"FROM {parent} parent WHERE parent.id = child.{fk} "
        "AND child.enterprise_id IS NULL"
    )


def upgrade() -> None:
    for table in TABLES:
        _add(table)
    for table in ("interventions", "rapports", "historiques", "depot_services"):
        _owner(table)
    _owner("notifications", "parent_user_id")
    _parent("intervention_produits", "interventions", "intervention_id")
    _parent("historiques_interventions", "interventions", "intervention_id")
    _parent("galerie_photos", "produits", "produit_id")
    _parent("depot_tarifs", "depot_services", "service_id")
    _parent("depots", "depot_services", "service_id")
    _parent("depot_tarif_item", "depots", "depot_id")
    _parent("factures_depot", "depots", "depot_id")

    for table in ("interventions", "rapports", "historiques", "depot_services"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}")
        op.execute(
            f"CREATE TRIGGER trg_{table}_assign_enterprise BEFORE INSERT OR UPDATE OF "
            f"user_id, enterprise_id ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION tradecare_assign_enterprise_from_owner()"
        )

    op.execute("""
        CREATE OR REPLACE FUNCTION tradecare_assign_operational_enterprise()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.enterprise_id IS NOT NULL THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'notifications' THEN
                SELECT e.id INTO NEW.enterprise_id FROM enterprise_groups g
                JOIN enterprises e ON e.group_id = g.id AND e.is_primary IS TRUE
                WHERE g.owner_user_id = NEW.parent_user_id LIMIT 1;
            ELSIF TG_TABLE_NAME IN ('intervention_produits', 'historiques_interventions') THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM interventions
                WHERE id = NEW.intervention_id;
            ELSIF TG_TABLE_NAME = 'galerie_photos' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM produits WHERE id = NEW.produit_id;
            ELSIF TG_TABLE_NAME IN ('depot_tarifs') THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM depot_services WHERE id = NEW.service_id;
            ELSIF TG_TABLE_NAME = 'depots' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM depot_services WHERE id = NEW.service_id;
            ELSIF TG_TABLE_NAME = 'depot_tarif_item' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM depots WHERE id = NEW.depot_id;
            ELSIF TG_TABLE_NAME = 'factures_depot' THEN
                SELECT enterprise_id INTO NEW.enterprise_id FROM depots WHERE id = NEW.depot_id;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    specs = {
        "notifications": "parent_user_id, enterprise_id",
        "intervention_produits": "intervention_id, enterprise_id",
        "historiques_interventions": "intervention_id, enterprise_id",
        "galerie_photos": "produit_id, enterprise_id",
        "depot_tarifs": "service_id, enterprise_id",
        "depots": "service_id, enterprise_id",
        "depot_tarif_item": "depot_id, enterprise_id",
        "factures_depot": "depot_id, enterprise_id",
    }
    for table, columns in specs.items():
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}")
        op.execute(
            f"CREATE TRIGGER trg_{table}_assign_enterprise BEFORE INSERT OR UPDATE OF "
            f"{columns} ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION tradecare_assign_operational_enterprise()"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_assign_enterprise ON {table}")
    op.execute("DROP FUNCTION IF EXISTS tradecare_assign_operational_enterprise()")
    for table in reversed(TABLES):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_enterprise_id")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_enterprise_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS enterprise_id")
