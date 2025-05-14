"""Ajout des tables unite_produit et rapports

Revision ID: add_unite_produit_and_rapport
Revises: xxxxxxxxxxxx
Create Date: 2025-05-12

"""
from alembic import op
import sqlalchemy as sa


# Identifiants
revision = 'add_unite_produit_and_rapport'
down_revision = '163a4ed76ebb'  # ⬅️ remplace par l'ID de la dernière migration réelle
branch_labels = None
depends_on = None


def upgrade():
    # 📦 Table unite_produit
    op.create_table(
        'unite_produit',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('produit_id', sa.Integer(), sa.ForeignKey('produits.id', ondelete="CASCADE"), nullable=False),
        sa.Column('tracabilite', sa.String(), unique=True, nullable=False),
        sa.Column('etat', sa.String(), default='en_stock'),
        sa.Column('date_creation', sa.DateTime(), server_default=sa.func.now())
    )

    # 📝 Table rapports
    op.create_table(
        'rapports',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('contenu', sa.Text(), nullable=False),
        sa.Column('date_creation', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete="SET NULL"), nullable=True),
        sa.Column('sub_user_id', sa.Integer(), sa.ForeignKey('sub_users.id', ondelete="SET NULL"), nullable=True)
    )


def downgrade():
    op.drop_table('rapports')
    op.drop_table('unite_produit')
