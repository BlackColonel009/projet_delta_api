from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class FactureDepot(Base):
    __tablename__ = "factures_depot"

    id = Column(Integer, primary_key=True, index=True)
    depot_id = Column(Integer, ForeignKey("depots.id"), nullable=False, unique=True)  # une facture par dépôt
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    date_facture = Column(DateTime, default=datetime.utcnow)

    montant_ht = Column(Float, nullable=False)
    tva = Column(Float, nullable=True, default=0.0)
    montant_ttc = Column(Float, nullable=False)

    statut = Column(String, default="en_attente")  # enum possible

    mode_paiement = Column(String, nullable=True)
    date_paiement = Column(DateTime, nullable=True)

    remarques = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    depot = relationship("Depot", back_populates="facture")
    client = relationship("Client")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 👈 nouvelle colonne
    user = relationship("User")  
