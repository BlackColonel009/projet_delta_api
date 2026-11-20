"""Add invoice discount and tax snapshot without altering existing totals."""
from alembic import op
import sqlalchemy as sa

revision = "n1k2l3m4n5o6"
down_revision = "m0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("factures", sa.Column("remise_ht", sa.Float(), nullable=False, server_default="0"))
    op.add_column("factures", sa.Column("taux_tva_snapshot", sa.Float(), nullable=True))
    op.add_column("factures", sa.Column("afficher_remise", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("factures", "afficher_remise")
    op.drop_column("factures", "taux_tva_snapshot")
    op.drop_column("factures", "remise_ht")
