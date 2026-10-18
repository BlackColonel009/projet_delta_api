"""optimize large operational lists

Revision ID: w4f5a6b7c8d9
Revises: v3e4f5a6b7c8
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op


revision: str = "w4f5a6b7c8d9"
down_revision: Union[str, None] = "v3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_clients_enterprise_id_desc", "clients", ["enterprise_id", "id"]
    )
    op.create_index(
        "ix_fournisseurs_enterprise_id_desc",
        "fournisseurs",
        ["enterprise_id", "id"],
    )
    op.create_index(
        "ix_unites_produit_enterprise_date",
        "unites_produit",
        ["enterprise_id", "date_creation"],
    )
    op.create_index(
        "ix_unites_produit_product_date",
        "unites_produit",
        ["produit_id", "date_creation"],
    )
    op.create_index(
        "ix_lignes_commandes_ventes_commande",
        "lignes_commandes_ventes",
        ["commande_id"],
    )
    op.create_index(
        "ix_lignes_commandes_achats_commande",
        "lignes_commandes_achats",
        ["commande_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lignes_commandes_achats_commande",
        table_name="lignes_commandes_achats",
    )
    op.drop_index(
        "ix_lignes_commandes_ventes_commande",
        table_name="lignes_commandes_ventes",
    )
    op.drop_index(
        "ix_unites_produit_product_date", table_name="unites_produit"
    )
    op.drop_index(
        "ix_unites_produit_enterprise_date", table_name="unites_produit"
    )
    op.drop_index(
        "ix_fournisseurs_enterprise_id_desc", table_name="fournisseurs"
    )
    op.drop_index("ix_clients_enterprise_id_desc", table_name="clients")
