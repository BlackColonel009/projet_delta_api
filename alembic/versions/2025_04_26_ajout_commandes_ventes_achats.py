"""Ajout Commandes Ventes et Achats

Revision ID: ajout_commandes_ventes_achats
Revises: ta_revision_precedente
Create Date: 2025-04-26

"""

from alembic import op
import sqlalchemy as sa


# Identifiants Alembic
revision = 'ajout_commandes_ventes_achats'
down_revision = '2936b268291a'  # mets ici l'ID de ta dernière migration
branch_labels = None
depends_on = None


def upgrade():
    # 📦 Table CommandeVente
    op.create_table(
        'commandes_ventes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('date_commande', sa.DateTime, nullable=False),
        sa.Column('total_ht', sa.Float, nullable=False, default=0),
        sa.Column('total_ttc', sa.Float, nullable=False, default=0),
        sa.Column('tva', sa.Float, nullable=False, default=0),
        sa.Column('tva_appliquee', sa.Boolean, default=False),
        sa.Column('statut', sa.String(length=50), default="en_attente"),
    )

    # 📦 Table LigneCommandeVente
    op.create_table(
        'lignes_commandes_ventes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('commande_id', sa.Integer, sa.ForeignKey('commandes_ventes.id'), nullable=False),
        sa.Column('produit_id', sa.Integer, sa.ForeignKey('produits.id'), nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('quantite', sa.Integer, nullable=False),
        sa.Column('prix_unitaire', sa.Float, nullable=False),
        sa.Column('total_ligne', sa.Float, nullable=False),
    )

    # 📦 Table CommandeAchat
    op.create_table(
        'commandes_achats',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('fournisseur_id', sa.Integer, sa.ForeignKey('fournisseurs.id'), nullable=False),
        sa.Column('date_commande', sa.DateTime, nullable=False),
        sa.Column('total_ht', sa.Float, nullable=False, default=0),
        sa.Column('total_ttc', sa.Float, nullable=False, default=0),
        sa.Column('tva', sa.Float, nullable=False, default=0),
        sa.Column('tva_appliquee', sa.Boolean, default=False),
        sa.Column('statut', sa.String(length=50), default="en_attente"),
    )

    # 📦 Table LigneCommandeAchat
    op.create_table(
        'lignes_commandes_achats',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('commande_id', sa.Integer, sa.ForeignKey('commandes_achats.id'), nullable=False),
        sa.Column('produit_id', sa.Integer, sa.ForeignKey('produits.id'), nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('quantite', sa.Integer, nullable=False),
        sa.Column('prix_unitaire', sa.Float, nullable=False),
        sa.Column('total_ligne', sa.Float, nullable=False),
    )


def downgrade():
    op.drop_table('lignes_commandes_achats')
    op.drop_table('commandes_achats')
    op.drop_table('lignes_commandes_ventes')
    op.drop_table('commandes_ventes')
