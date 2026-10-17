"""add invoice agent visibility setting

Revision ID: s0b1c2d3e4f5
Revises: r9a0b1c2d3e4
Create Date: 2026-10-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "s0b1c2d3e4f5"
down_revision: Union[str, None] = "r9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprises",
        sa.Column(
            "show_invoice_agent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("enterprises", "show_invoice_agent")
