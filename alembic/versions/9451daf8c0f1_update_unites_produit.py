"""update unites_produit

Revision ID: 9451daf8c0f1
Revises: add_unite_produit_and_rapport
Create Date: 2025-05-12 17:02:53.369682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9451daf8c0f1'
down_revision: Union[str, None] = 'add_unite_produit_and_rapport'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
