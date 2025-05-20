"""add code_barre to unites_produit

Revision ID: 5eab27090899
Revises: a0b843744878
Create Date: 2025-05-16 09:56:34.628007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eab27090899'
down_revision: Union[str, None] = 'a0b843744878'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
