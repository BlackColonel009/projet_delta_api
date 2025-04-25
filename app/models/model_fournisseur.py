# 📦 MODELE FOURNISSEUR SQLALCHEMY
# Fichier : app/models/model_fournisseur.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class Fournisseur(Base):
    __tablename__ = "fournisseurs"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    email = Column(String, nullable=True)
    telephone = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    type_fourniture = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Fournisseur {self.nom}>"