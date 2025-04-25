# 📦 MODELE CATEGORIE SQLALCHEMY
# Fichier : app/models/model_categorie.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class Categorie(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Categorie {self.nom}>"
