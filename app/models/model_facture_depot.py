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
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    user = relationship("User", foreign_keys=[user_id])

    issued_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_by_sub_user_id = Column(Integer, ForeignKey("sub_users.id"), nullable=True)
    issuer_name_snapshot = Column(String(160), nullable=True)
    issuer_role_snapshot = Column(String(80), nullable=True)
    invoice_color_snapshot = Column(String(16), nullable=True)
    simple_template_snapshot = Column(String(48), nullable=True)
    professional_template_snapshot = Column(String(48), nullable=True)
