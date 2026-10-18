# 📦 MODELE FOURNISSEUR SQLALCHEMY
# Fichier : app/models/model_fournisseur.py

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Index
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Fournisseur(Base):
    __tablename__ = "fournisseurs"
    __table_args__ = (
        Index("ix_fournisseurs_enterprise_id_desc", "enterprise_id", "id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    email = Column(String, nullable=True)
    telephone = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    type_fourniture = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    user = relationship("User", backref="fournisseurs")
    commandes = relationship("CommandeAchat", back_populates="fournisseur", cascade="all, delete")
    factures = relationship("Facture", back_populates="fournisseur")

    def __repr__(self):
        return f"<Fournisseur {self.nom}>"
