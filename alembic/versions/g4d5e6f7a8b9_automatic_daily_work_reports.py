"""automatic daily work reports

Revision ID: g4d5e6f7a8b9
Revises: f3c4d5e6f7a8
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = "g4d5e6f7a8b9"
down_revision = "f3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("enterprises", sa.Column("automatic_work_report_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("enterprises", sa.Column("automatic_work_report_inherit_time", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("enterprises", sa.Column("automatic_work_report_hour", sa.Integer(), nullable=False, server_default="18"))
    op.add_column("enterprises", sa.Column("automatic_work_report_minute", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("enterprises", sa.Column("automatic_work_report_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column(
        "rapports",
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
    )
    op.add_column("rapports", sa.Column("source_date", sa.Date(), nullable=True))
    op.create_unique_constraint(
        "uq_rapports_enterprise_source_date",
        "rapports",
        ["enterprise_id", "source", "source_date"],
    )


def downgrade():
    op.drop_constraint(
        "uq_rapports_enterprise_source_date", "rapports", type_="unique"
    )
    op.drop_column("rapports", "source_date")
    op.drop_column("rapports", "source")
    op.drop_column("enterprises", "automatic_work_report_minute")
    op.drop_column("enterprises", "automatic_work_report_config")
    op.drop_column("enterprises", "automatic_work_report_hour")
    op.drop_column("enterprises", "automatic_work_report_inherit_time")
    op.drop_column("enterprises", "automatic_work_report_enabled")
