"""seed director role

Revision ID: p7e8f9a0b1c2
Revises: o6d7e8f9a0b1
Create Date: 2026-10-16
"""
from typing import Sequence, Union
from alembic import op

revision: str = "p7e8f9a0b1c2"
down_revision: Union[str, None] = "o6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("INSERT INTO roles (name) VALUES ('Directeur') ON CONFLICT (name) DO NOTHING")


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'Directeur'")
