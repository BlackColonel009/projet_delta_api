"""add code_barre to unites_produit

Revision ID: 8705b7564d76
Revises: 010dfe3a02ad
Create Date: 2025-05-16 10:00:22.917614

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8705b7564d76'
down_revision: Union[str, None] = '010dfe3a02ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
