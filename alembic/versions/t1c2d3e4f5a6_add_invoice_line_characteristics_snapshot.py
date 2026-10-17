"""add invoice line characteristics snapshot

Revision ID: t1c2d3e4f5a6
Revises: s0b1c2d3e4f5
Create Date: 2026-10-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "t1c2d3e4f5a6"
down_revision: Union[str, None] = "s0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lignes_facture",
        sa.Column("caracteristiques_snapshot", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE lignes_facture AS line
        SET caracteristiques_snapshot = product.caracteristiques
        FROM produits AS product
        WHERE line.produit_id = product.id
          AND line.caracteristiques_snapshot IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("lignes_facture", "caracteristiques_snapshot")
