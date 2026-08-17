from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Depot(Base):
    __tablename__ = "depots"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("depot_services.id"), nullable=False)
    tarif_id = Column(Integer, ForeignKey("depot_tarifs.id"), nullable=True)

    description_bien = Column(String, nullable=False)
    date_depot = Column(DateTime, default=datetime.utcnow)
    date_retrait = Column(DateTime, nullable=True)
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
    user = relationship("User", back_populates="depots")



    def __repr__(self):
        return f"<Depot {self.description_bien} - Client {self.client_id}>"
