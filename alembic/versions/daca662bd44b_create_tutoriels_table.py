"""create tutoriels table

Revision ID: daca662bd44b
Revises: e0043c9dac31
Create Date: 2025-06-01 12:36:04.460383

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'daca662bd44b'
down_revision: Union[str, None] = 'e0043c9dac31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
