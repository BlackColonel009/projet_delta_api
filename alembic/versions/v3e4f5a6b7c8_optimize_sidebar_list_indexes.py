"""optimize sidebar list indexes

Revision ID: v3e4f5a6b7c8
Revises: u2d3e4f5a6b7
Create Date: 2026-10-17

"""
from typing import Sequence, Union

from alembic import op


revision: str = "v3e4f5a6b7c8"
down_revision: Union[str, None] = "u2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_rapports_enterprise_date",
        "rapports",
        ["enterprise_id", "date_creation"],
        unique=False,
    )
    op.create_index(
        "ix_commandes_ventes_enterprise_date",
        "commandes_ventes",
        ["enterprise_id", "date_commande"],
        unique=False,
    )
    op.create_index(
        "ix_commandes_achats_enterprise_date",
        "commandes_achats",
        ["enterprise_id", "date_commande"],
        unique=False,
    )
    op.create_index(
        "ix_depots_enterprise_date",
        "depots",
        ["enterprise_id", "date_depot"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_depots_enterprise_date", table_name="depots")
    op.drop_index(
        "ix_commandes_achats_enterprise_date",
        table_name="commandes_achats",
    )
    op.drop_index(
        "ix_commandes_ventes_enterprise_date",
        table_name="commandes_ventes",
    )
    op.drop_index("ix_rapports_enterprise_date", table_name="rapports")
