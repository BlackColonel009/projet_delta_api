# depot_tarif_item.py

from sqlalchemy import Column, Integer, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database import Base

class DepotTarifItem(Base):
    __tablename__ = "depot_tarif_item"

    id = Column(Integer, primary_key=True, index=True)
    depot_id = Column(Integer, ForeignKey("depots.id", ondelete="CASCADE"))
    tarif_id = Column(Integer, ForeignKey("depot_tarifs.id"))
    quantite = Column(Integer, default=1)
    prix_personnalise = Column(Float, nullable=True)
    description = Column(String, nullable=True)

   

    depot = relationship("Depot", back_populates="tarif_items")
    tarif = relationship("DepotTarif")
