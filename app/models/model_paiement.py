from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Paiement(Base):
    __tablename__ = "paiements"

    id = Column(Integer, primary_key=True)
    facture_id = Column(Integer, ForeignKey("factures.id"), nullable=False)
    montant = Column(Float, nullable=False)
    date_paiement = Column(DateTime, default=datetime.utcnow)
    moyen_paiement = Column(String, default="espèces")  # espèces, virement, mobile money, etc.
    devise = Column(String, default="FCFA")#dans une liste déroulante on laisse choisir l'utilisateur

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", backref="paiements")

    facture = relationship("Facture", back_populates="paiements")
