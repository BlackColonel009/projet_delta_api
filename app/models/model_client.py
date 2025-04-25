# 📦 MODELE CLIENT SQLALCHEMY
# Fichier : app/models/model_client.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    entreprise = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Client {self.nom}>"
