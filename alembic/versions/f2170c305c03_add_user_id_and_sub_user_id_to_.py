"""Add user_id and sub_user_id to historique tables

Revision ID: f2170c305c03
Revises: 9aba1698cbfa
Create Date: 2025-05-06 04:16:37.410587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2170c305c03'
down_revision: Union[str, None] = '9aba1698cbfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
