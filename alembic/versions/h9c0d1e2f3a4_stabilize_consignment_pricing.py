"""stabilize consignment pricing and ownership constraints

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE depot_services DROP CONSTRAINT IF EXISTS "
        "depot_services_nom_key"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_depot_service_company_name "
        "ON depot_services (user_id, lower(nom))"
    )
    op.execute(
        "ALTER TABLE depot_tarif_item ADD COLUMN IF NOT EXISTS "
        "mode_tarification_snapshot VARCHAR NOT NULL DEFAULT 'unitaire'"
    )
    op.execute(
        "ALTER TABLE depot_tarif_item ADD COLUMN IF NOT EXISTS "
        "prix_unitaire_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE depot_tarif_item ADD COLUMN IF NOT EXISTS "
        "montant_total DOUBLE PRECISION NOT NULL DEFAULT 0"
    )
    op.execute(
        "UPDATE depot_tarif_item AS item SET "
        "mode_tarification_snapshot = CASE "
        "WHEN lower(COALESCE(t.mode_tarification, '')) IN "
        "('duree', 'durée', 'minute', 'minutes') THEN 'duree' "
        "ELSE 'unitaire' END, "
        "prix_unitaire_snapshot = CASE "
        "WHEN item.prix_personnalise IS NOT NULL THEN item.prix_personnalise "
        "WHEN lower(COALESCE(t.mode_tarification, '')) IN "
        "('duree', 'durée', 'minute', 'minutes') "
        "THEN COALESCE(t.tarif_par_minute, 0) "
        "ELSE COALESCE(t.tarif_unitaire, 0) END "
        "FROM depot_tarifs AS t WHERE t.id = item.tarif_id"
    )
    op.execute(
        "UPDATE depot_tarif_item SET montant_total = "
        "CASE WHEN mode_tarification_snapshot = 'unitaire' "
        "OR prix_personnalise IS NOT NULL "
        "THEN prix_unitaire_snapshot * quantite ELSE 0 END"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_depot_service_company_name")
    # Ne pas restaurer l'ancienne unicité globale : après utilisation, deux
    # entreprises peuvent légitimement posséder un service portant le même nom.
    # La recréer rendrait le rollback impossible sur des données valides.
    op.execute(
        "ALTER TABLE depot_tarif_item DROP COLUMN IF EXISTS montant_total"
    )
    op.execute(
        "ALTER TABLE depot_tarif_item DROP COLUMN IF EXISTS "
        "prix_unitaire_snapshot"
    )
    op.execute(
        "ALTER TABLE depot_tarif_item DROP COLUMN IF EXISTS "
        "mode_tarification_snapshot"
    )
