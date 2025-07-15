# 📦 MODELE CLIENT SQLALCHEMY
# Fichier : app/models/model_client.py

from sqlalchemy import Column, ForeignKey,  Integer, String, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    entreprise = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="clients")
    commandes = relationship("CommandeVente", back_populates="client")
    factures = relationship("Facture", back_populates="client")
    produits_achetes = relationship("ClientProduit", back_populates="client", cascade="all, delete-orphan")
    def __repr__(self):
        return f"<Client {self.nom}>"
