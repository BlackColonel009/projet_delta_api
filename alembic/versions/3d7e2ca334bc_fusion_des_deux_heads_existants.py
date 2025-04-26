"""Fusion des deux heads existants

Revision ID: 3d7e2ca334bc
Revises: ajout_commandes_ventes_achats, ce7989514af6
Create Date: 2025-04-25 23:15:56.361138

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d7e2ca334bc'
down_revision: Union[str, None] = ('ajout_commandes_ventes_achats', 'ce7989514af6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
