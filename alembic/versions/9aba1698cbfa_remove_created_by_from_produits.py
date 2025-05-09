"""remove created_by from produits

Revision ID: 9aba1698cbfa
Revises: 2027075f616a
Create Date: 2025-05-05 00:52:07.418565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9aba1698cbfa'
down_revision: Union[str, None] = '2027075f616a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
