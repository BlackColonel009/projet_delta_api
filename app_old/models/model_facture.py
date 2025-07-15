# 📦 MODELES POUR FACTURATION
# Fichier : app/models/model_facture.py

from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
from app.database import Base

class TypeFacture(PyEnum):
    achat = "achat"
    vente = "vente"
    devis = "devis"
    proforma = "proforma"

class Facture(Base):
    __tablename__ = "factures"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(TypeFacture), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)
    statut = Column(String, default="en attente")  # ex: brouillon, envoyé, payé, annulé
    remarques = Column(Text, nullable=True)
    total_ht = Column(Float, default=0.0)
    total_ttc = Column(Float, default=0.0)
    tva = Column(Float, default=0.0)
    devise = Column(String, default="FCFA")
    
    commande_achat_id = Column(Integer, ForeignKey("commandes_achats.id"), nullable=True)
    commande_id = Column(Integer, ForeignKey("commandes_ventes.id"), nullable=True)
    commande = relationship("CommandeVente")

    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="factures")

    sub_user_id = Column(Integer, ForeignKey("sub_users.id"), nullable=True)
    sub_user = relationship("SubUser")


    client = relationship("Client", back_populates="factures")

    fournisseur = relationship("Fournisseur", back_populates="factures")

    lignes = relationship("LigneFacture", back_populates="facture", cascade="all, delete")
    paiements = relationship("Paiement", back_populates="facture", cascade="all, delete")

class LigneFacture(Base):
    __tablename__ = "lignes_facture"

    id = Column(Integer, primary_key=True, index=True)
    facture_id = Column(Integer, ForeignKey("factures.id"))
    produit_id = Column(Integer, ForeignKey("produits.id"))
    description = Column(String, nullable=False)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    total_ligne = Column(Float, nullable=False)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="lignes_facture")



    facture = relationship("Facture", back_populates="lignes")
    produit = relationship("Produit")
