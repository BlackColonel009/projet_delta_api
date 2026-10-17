"""add immutable invoice issuance snapshots

Revision ID: r9a0b1c2d3e4
Revises: q8f9a0b1c2d3
Create Date: 2026-10-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "r9a0b1c2d3e4"
down_revision: Union[str, None] = "q8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SNAPSHOT_COLUMNS = (
    ("issued_by_user_id", sa.Integer()),
    ("issued_by_sub_user_id", sa.Integer()),
    ("issuer_name_snapshot", sa.String(length=160)),
    ("issuer_role_snapshot", sa.String(length=80)),
    ("invoice_color_snapshot", sa.String(length=16)),
    ("simple_template_snapshot", sa.String(length=48)),
    ("professional_template_snapshot", sa.String(length=48)),
)


def _add_snapshots(table_name: str) -> None:
    for name, type_ in SNAPSHOT_COLUMNS:
        op.add_column(table_name, sa.Column(name, type_, nullable=True))
    op.create_foreign_key(
        f"fk_{table_name}_issued_by_user_id",
        table_name,
        "users",
        ["issued_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        f"fk_{table_name}_issued_by_sub_user_id",
        table_name,
        "sub_users",
        ["issued_by_sub_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _backfill_snapshots(table_name: str, date_column: str) -> None:
    op.execute(
        f"UPDATE {table_name} f SET "
        "issued_by_sub_user_id = f.sub_user_id "
        "WHERE f.sub_user_id IS NOT NULL"
        if table_name == "factures"
        else f"UPDATE {table_name} SET issued_by_user_id = user_id"
    )
    if table_name == "factures":
        op.execute(
            "UPDATE factures SET issued_by_user_id = user_id "
            "WHERE sub_user_id IS NULL"
        )
        op.execute(
            "UPDATE factures f SET issuer_name_snapshot = s.username, "
            "issuer_role_snapshot = s.role FROM sub_users s "
            "WHERE f.issued_by_sub_user_id = s.id"
        )
    op.execute(
        f"UPDATE {table_name} f SET "
        "issuer_name_snapshot = COALESCE(f.issuer_name_snapshot, u.username, u.email), "
        "issuer_role_snapshot = COALESCE(f.issuer_role_snapshot, 'Propriétaire') "
        "FROM users u WHERE f.user_id = u.id"
    )
    op.execute(
        f"UPDATE {table_name} f SET "
        "invoice_color_snapshot = e.invoice_color, "
        "simple_template_snapshot = e.simple_invoice_template, "
        "professional_template_snapshot = e.professional_invoice_template "
        "FROM enterprises e WHERE f.enterprise_id = e.id"
    )
    op.execute(
        f"UPDATE {table_name} f SET "
        "invoice_color_snapshot = COALESCE(f.invoice_color_snapshot, u.facture_color, '#5C6BC0') "
        "FROM users u WHERE f.user_id = u.id"
    )
    op.execute(
        f"UPDATE {table_name} SET "
        "invoice_color_snapshot = COALESCE(invoice_color_snapshot, '#5C6BC0'), "
        "simple_template_snapshot = COALESCE(simple_template_snapshot, 'simple_classic'), "
        "professional_template_snapshot = COALESCE(professional_template_snapshot, 'professional_signature')"
    )


def upgrade() -> None:
    op.add_column(
        "enterprises",
        sa.Column(
            "simple_invoice_template",
            sa.String(length=48),
            nullable=False,
            server_default="simple_classic",
        ),
    )
    op.add_column(
        "enterprises",
        sa.Column(
            "professional_invoice_template",
            sa.String(length=48),
            nullable=False,
            server_default="professional_signature",
        ),
    )
    op.add_column(
        "factures",
        sa.Column("technical_created_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        "UPDATE factures SET technical_created_at = "
        "COALESCE(date_creation, CURRENT_TIMESTAMP)"
    )
    op.alter_column("factures", "technical_created_at", nullable=False)
    _add_snapshots("factures")
    _add_snapshots("factures_depot")
    _backfill_snapshots("factures", "date_creation")
    _backfill_snapshots("factures_depot", "date_facture")


def downgrade() -> None:
    for table_name in ("factures_depot", "factures"):
        op.drop_constraint(
            f"fk_{table_name}_issued_by_sub_user_id",
            table_name,
            type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_{table_name}_issued_by_user_id",
            table_name,
            type_="foreignkey",
        )
        for name, _ in reversed(SNAPSHOT_COLUMNS):
            op.drop_column(table_name, name)
    op.drop_column("factures", "technical_created_at")
    op.drop_column("enterprises", "professional_invoice_template")
    op.drop_column("enterprises", "simple_invoice_template")
