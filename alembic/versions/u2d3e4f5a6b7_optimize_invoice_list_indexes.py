"""optimize invoice list indexes

Revision ID: u2d3e4f5a6b7
Revises: t1c2d3e4f5a6
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op


revision: str = "u2d3e4f5a6b7"
down_revision: Union[str, None] = "t1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_factures_enterprise_date",
        "factures",
        ["enterprise_id", "date_creation"],
        unique=False,
    )
    op.create_index(
        "ix_paiements_facture_id",
        "paiements",
        ["facture_id"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_facture_facture_id",
        "lignes_facture",
        ["facture_id"],
        unique=False,
    )
    op.create_index(
        "ix_produits_enterprise_active_date",
        "produits",
        ["enterprise_id", "date_suppression", "date_creation"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_produits_enterprise_active_date", table_name="produits")
    op.drop_index("ix_lignes_facture_facture_id", table_name="lignes_facture")
    op.drop_index("ix_paiements_facture_id", table_name="paiements")
    op.drop_index("ix_factures_enterprise_date", table_name="factures")
