# 📦 MODELE ACHAT SQLALCHEMY
# Fichier : app/models/model_achat.py

from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Achat(Base):
    __tablename__ = "achats"

    id = Column(Integer, primary_key=True, index=True)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"), nullable=False)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    date_achat = Column(DateTime, default=datetime.utcnow)

    # Relations
    produit = relationship("Produit", backref="achats")
    fournisseur = relationship("Fournisseur", backref="achats")

    def __repr__(self):
        return f"<Achat produit={self.produit_id} fournisseur={self.fournisseur_id}>"