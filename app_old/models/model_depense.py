from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Depense(Base):
    __tablename__ = "depenses"

    id = Column(Integer, primary_key=True, index=True)
    libelle = Column(String, nullable=False)
    montant = Column(Float, nullable=False)
    categorie = Column(String, default="Divers")  # Exemples : Loyer, Internet, Transport, Salaires
    date_depense = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="depenses")