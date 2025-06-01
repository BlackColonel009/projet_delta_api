"""create tutoriels table

Revision ID: 9301d49f921e
Revises: daca662bd44b
Create Date: 2025-06-01 12:37:39.854373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9301d49f921e'
down_revision: Union[str, None] = 'daca662bd44b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
