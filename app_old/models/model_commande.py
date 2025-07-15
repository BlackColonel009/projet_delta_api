# 📦 MODELS POUR CommandeVente et CommandeAchat

from sqlalchemy import Column, ForeignKey, Integer, Float, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class CommandeVente(Base):
    __tablename__ = "commandes_ventes"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    date_commande = Column(DateTime, default=datetime.utcnow)
    total_ht = Column(Float, default=0)
    total_ttc = Column(Float, default=0)
    tva = Column(Float, default=0)
    tva_appliquee = Column(Boolean, default=False)
    statut = Column(String, default="en_attente")

    unites_vendues = relationship("UniteProduit", back_populates="commande_vente")


    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", backref="commandes_ventes")



    client = relationship("Client", back_populates="commandes")
    lignes = relationship("LigneCommandeVente", back_populates="commande", cascade="all, delete")


class LigneCommandeVente(Base):
    __tablename__ = "lignes_commandes_ventes"

    id = Column(Integer, primary_key=True, index=True)
    commande_id = Column(Integer, ForeignKey("commandes_ventes.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    description = Column(String)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    total_ligne = Column(Float, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", backref="lignes_commandes_ventes")

    commande = relationship("CommandeVente", back_populates="lignes")
    produit = relationship("Produit")


class CommandeAchat(Base):
    __tablename__ = "commandes_achats"

    id = Column(Integer, primary_key=True, index=True)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=False)
    date_commande = Column(DateTime, default=datetime.utcnow)
    total_ht = Column(Float, default=0)
    total_ttc = Column(Float, default=0)
    tva = Column(Float, default=0)
    tva_appliquee = Column(Boolean, default=False)
    statut = Column(String, default="en_attente")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", backref="commandes_achats")


    fournisseur = relationship("Fournisseur", back_populates="commandes")
    lignes = relationship("LigneCommandeAchat", back_populates="commande", cascade="all, delete")


class LigneCommandeAchat(Base):
    __tablename__ = "lignes_commandes_achats"

    id = Column(Integer, primary_key=True, index=True)
    commande_id = Column(Integer, ForeignKey("commandes_achats.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    description = Column(String)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    total_ligne = Column(Float, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", backref="lignes_commandes_achats")

    commande = relationship("CommandeAchat", back_populates="lignes")
    produit = relationship("Produit")