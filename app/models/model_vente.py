# 📦 MODELE VENTE SQLALCHEMY
# Fichier : app/models/model_vente.py

from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Vente(Base):
    __tablename__ = "ventes"

    id = Column(Integer, primary_key=True, index=True)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    quantite = Column(Integer, nullable=False)
    prix_total = Column(Float, nullable=False)
    date_vente = Column(DateTime, default=datetime.utcnow)

    # Relations
    produit = relationship("Produit", backref="ventes")
    client = relationship("Client", backref="ventes")

    def __repr__(self):
        return f"<Vente produit={self.produit_id} client={self.client_id}>"