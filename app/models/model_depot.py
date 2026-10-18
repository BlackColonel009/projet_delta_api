from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Index
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Depot(Base):
    __tablename__ = "depots"
    __table_args__ = (
        Index("ix_depots_enterprise_date", "enterprise_id", "date_depot"),
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("depot_services.id"), nullable=False)
    tarif_id = Column(Integer, ForeignKey("depot_tarifs.id"), nullable=True)

    description_bien = Column(String, nullable=False)
    date_depot = Column(DateTime, default=datetime.utcnow)
    date_stockage = Column(DateTime, nullable=True)
    date_pret_retrait = Column(DateTime, nullable=True)
    date_retrait = Column(DateTime, nullable=True)
    date_annulation = Column(DateTime, nullable=True)
    motif_annulation = Column(String, nullable=True)
    statut_modifie_le = Column(DateTime, nullable=True)
    statut_modifie_par = Column(Integer, ForeignKey("users.id"), nullable=True)
    statut = Column(String, default="en_attente")

    quantite = Column(Integer, nullable=False, default=1)
    prix_personnalise = Column(Float, nullable=True)
    duree_minutes = Column(Integer, nullable=True)
    prix_total = Column(Float, nullable=True)

    tarif_items = relationship("DepotTarifItem", back_populates="depot", cascade="all, delete-orphan")

    client = relationship("Client", back_populates="depots")

    service = relationship("DepotService")
    tarif = relationship("DepotTarif")

    facture = relationship("FactureDepot", back_populates="depot", uselist=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # <-- nouveau champ
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    user = relationship("User", back_populates="depots", foreign_keys=[user_id])

    @property
    def facture_depot_id(self):
        return self.facture.id if self.facture else None


    def __repr__(self):
        return f"<Depot {self.description_bien} - Client {self.client_id}>"
