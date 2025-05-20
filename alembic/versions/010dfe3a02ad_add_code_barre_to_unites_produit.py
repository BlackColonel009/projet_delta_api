"""add code_barre to unites_produit

Revision ID: 010dfe3a02ad
Revises: 5eab27090899
Create Date: 2025-05-16 10:00:22.188564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010dfe3a02ad'
down_revision: Union[str, None] = '5eab27090899'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
