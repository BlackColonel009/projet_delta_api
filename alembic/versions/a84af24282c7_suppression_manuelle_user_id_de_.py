"""Suppression manuelle user_id de Intervention

Revision ID: a84af24282c7
Revises: 428a03b72d88
Create Date: 2025-05-03 03:39:08.645548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a84af24282c7'
down_revision: Union[str, None] = '428a03b72d88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
