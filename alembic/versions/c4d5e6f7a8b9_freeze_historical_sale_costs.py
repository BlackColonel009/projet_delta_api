"""freeze historical purchase costs on sale and invoice lines

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lignes_commandes_ventes",
        sa.Column(
            "cout_achat_unitaire",
            sa.Float(),
            nullable=True,
            server_default="0",
        ),
    )
    op.add_column(
        "lignes_facture",
        sa.Column(
            "cout_achat_unitaire",
            sa.Float(),
            nullable=True,
            server_default="0",
        ),
    )

    # Pour l'historique, on recherche d'abord le dernier prix d'achat connu
    # avant la vente. Le prix actuel du produit n'est qu'un repli.
    op.execute(
        """
        UPDATE lignes_commandes_ventes AS lcv
        SET cout_achat_unitaire = COALESCE(
            (
                SELECT lca.prix_unitaire
                FROM lignes_commandes_achats AS lca
                JOIN commandes_achats AS ca ON ca.id = lca.commande_id
                JOIN commandes_ventes AS cv ON cv.id = lcv.commande_id
                WHERE lca.produit_id = lcv.produit_id
                  AND ca.user_id = cv.user_id
                  AND ca.date_commande <= cv.date_commande
                ORDER BY ca.date_commande DESC, lca.id DESC
                LIMIT 1
            ),
            (SELECT p.prix_achat FROM produits AS p WHERE p.id = lcv.produit_id),
            0
        )
        """
    )
    op.execute(
        """
        UPDATE lignes_facture AS lf
        SET cout_achat_unitaire = COALESCE(
            (
                SELECT lcv.cout_achat_unitaire
                FROM factures AS f
                JOIN lignes_commandes_ventes AS lcv
                  ON lcv.commande_id = f.commande_id
                 AND lcv.produit_id = lf.produit_id
                WHERE f.id = lf.facture_id
                ORDER BY lcv.id DESC
                LIMIT 1
            ),
            (
                SELECT lca.prix_unitaire
                FROM factures AS f
                JOIN lignes_commandes_achats AS lca
                  ON lca.produit_id = lf.produit_id
                JOIN commandes_achats AS ca ON ca.id = lca.commande_id
                WHERE f.id = lf.facture_id
                  AND ca.user_id = f.user_id
                  AND ca.date_commande <= f.date_creation
                ORDER BY ca.date_commande DESC, lca.id DESC
                LIMIT 1
            ),
            (SELECT p.prix_achat FROM produits AS p WHERE p.id = lf.produit_id),
            0
        )
        """
    )

    op.alter_column(
        "lignes_commandes_ventes",
        "cout_achat_unitaire",
        existing_type=sa.Float(),
        nullable=False,
        server_default="0",
    )
    op.alter_column(
        "lignes_facture",
        "cout_achat_unitaire",
        existing_type=sa.Float(),
        nullable=False,
        server_default="0",
    )


def downgrade() -> None:
    op.drop_column("lignes_facture", "cout_achat_unitaire")
    op.drop_column("lignes_commandes_ventes", "cout_achat_unitaire")
