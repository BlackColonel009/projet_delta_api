"""add user session lock settings

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "session_lock_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("session_lock_password_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "session_lock_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "sub_users",
        sa.Column(
            "session_lock_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "sub_users",
        sa.Column("session_lock_password_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "sub_users",
        sa.Column(
            "session_lock_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_check_constraint(
        "ck_users_session_lock_minutes",
        "users",
        "session_lock_minutes IN (0, 5, 15, 30, 60)",
    )
    op.create_check_constraint(
        "ck_sub_users_session_lock_minutes",
        "sub_users",
        "session_lock_minutes IN (0, 5, 15, 30, 60)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_sub_users_session_lock_minutes",
        "sub_users",
        type_="check",
    )
    op.drop_constraint(
        "ck_users_session_lock_minutes",
        "users",
        type_="check",
    )
    op.drop_column("sub_users", "session_lock_minutes")
    op.drop_column("sub_users", "session_lock_password_hash")
    op.drop_column("sub_users", "session_lock_configured")
    op.drop_column("users", "session_lock_minutes")
    op.drop_column("users", "session_lock_password_hash")
    op.drop_column("users", "session_lock_configured")
