"""stock arrivals and inter-enterprise transfers

Revision ID: h5e6f7a8b9c0
Revises: g4d5e6f7a8b9
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa


revision = "h5e6f7a8b9c0"
down_revision = "g4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("produits", sa.Column("catalog_key", sa.String(36), nullable=True))
    op.create_index("ix_produits_catalog_key", "produits", ["catalog_key"])
    op.create_index(
        "uq_produits_enterprise_catalog_key",
        "produits",
        ["enterprise_id", "catalog_key"],
        unique=True,
        postgresql_where=sa.text("catalog_key IS NOT NULL"),
    )

    op.create_table(
        "stock_arrivals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("fournisseurs.id"), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_name", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'validated', 'cancelled')", name="ck_stock_arrivals_status"),
    )
    op.create_index("ix_stock_arrivals_enterprise_created", "stock_arrivals", ["enterprise_id", "created_at"])
    op.create_table(
        "stock_arrival_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arrival_id", sa.Integer(), sa.ForeignKey("stock_arrivals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("barcodes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_arrival_lines_quantity"),
    )
    op.create_index("ix_stock_arrival_lines_arrival_product", "stock_arrival_lines", ["arrival_id", "product_id"])
    op.create_table(
        "stock_arrival_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("arrival_line_id", sa.Integer(), sa.ForeignKey("stock_arrival_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("unites_produit.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("barcode_snapshot", sa.String(), nullable=True),
        sa.Column("traceability_snapshot", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stock_arrival_units_line", "stock_arrival_units", ["arrival_line_id"])
    op.create_index("ix_stock_arrival_units_unit", "stock_arrival_units", ["unit_id"], unique=True)

    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("destination_enterprise_id", sa.Integer(), sa.ForeignKey("enterprises.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_arrival_id", sa.Integer(), sa.ForeignKey("stock_arrivals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_name", sa.String(180), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('completed', 'cancelled')", name="ck_stock_transfers_status"),
    )
    op.create_index("ix_stock_transfers_source_created", "stock_transfers", ["source_enterprise_id", "created_at"])
    op.create_index("ix_stock_transfers_destination_created", "stock_transfers", ["destination_enterprise_id", "created_at"])
    op.create_table(
        "stock_transfer_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transfer_id", sa.Integer(), sa.ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_product_id", sa.Integer(), sa.ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("destination_product_id", sa.Integer(), sa.ForeignKey("produits.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_transfer_lines_quantity"),
    )
    op.create_table(
        "stock_transfer_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transfer_line_id", sa.Integer(), sa.ForeignKey("stock_transfer_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("unites_produit.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("barcode_snapshot", sa.String(), nullable=True),
        sa.Column("traceability_snapshot", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stock_transfer_units_line", "stock_transfer_units", ["transfer_line_id"])


def downgrade():
    op.drop_table("stock_transfer_units")
    op.drop_table("stock_transfer_lines")
    op.drop_table("stock_transfers")
    op.drop_table("stock_arrival_units")
    op.drop_table("stock_arrival_lines")
    op.drop_table("stock_arrivals")
    op.drop_index("uq_produits_enterprise_catalog_key", table_name="produits")
    op.drop_index("ix_produits_catalog_key", table_name="produits")
    op.drop_column("produits", "catalog_key")
