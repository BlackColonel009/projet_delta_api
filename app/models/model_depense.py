from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base

class Depense(Base):
    __tablename__ = "depenses"

    id = Column(Integer, primary_key=True, index=True)
    libelle = Column(String, nullable=False)
    montant = Column(Float, nullable=False)
    categorie = Column(String, default="Divers")  # Exemples : Loyer, Internet, Transport, Salaires
    date_depense = Column(DateTime, default=datetime.utcnow)
