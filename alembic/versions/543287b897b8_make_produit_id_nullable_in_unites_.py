"""make produit_id nullable in unites_produit

Revision ID: 543287b897b8
Revises: 8705b7564d76
Create Date: 2025-05-16 17:18:38.742294

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '543287b897b8'
down_revision: Union[str, None] = '8705b7564d76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
