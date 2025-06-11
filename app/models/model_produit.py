# 📦 MODELE PRODUIT SQLALCHEMY
# Fichier : app/models/model_produit.py

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.model_galerie import GaleriePhoto



class Produit(Base):
    __tablename__ = "produits"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    categorie_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    prix_achat = Column(Float, nullable=False)
    prix_vente = Column(Float, nullable=False)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=True)
    quantite = Column(Integer, default=0)
    rating = Column(Float, nullable=True)
    caracteristiques = Column(Text, nullable=True)
    couleur = Column(String, nullable=True)
    etat = Column(String, default="oui")  # oui ou non
    commentaire = Column(Text, nullable=True)
    is_installe = Column(Boolean, default=False)
    tracabilite = Column(String, nullable=True)  # lien vers code QR
    emplacement = Column(String, default="magasin")
    image_url = Column(String, nullable=True)
    stock_min = Column(Integer, default=0)
    a_des_barcodes = Column(Boolean, default=False)

    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="produits")

    date_creation = Column(DateTime, default=datetime.utcnow)
    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date_suppression = Column(DateTime, nullable=True)

    # Relations (à ajouter si besoin)
    categorie = relationship("Categorie", backref="produits")
    fournisseur = relationship("Fournisseur", backref="produits")

    unites = relationship("UniteProduit", back_populates="produit", cascade="all, delete")

    galerie = relationship("GaleriePhoto", back_populates="produit", cascade="all, delete")


    def __repr__(self):
        return f"<Produit {self.nom}>"
