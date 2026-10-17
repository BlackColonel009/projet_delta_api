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
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    # Instantané financier : une modification ultérieure du catalogue ne doit
    # jamais changer le montant historique d'un dépôt.
    mode_tarification_snapshot = Column(String, nullable=False, default="unitaire")
    prix_unitaire_snapshot = Column(Float, nullable=False, default=0)
    montant_total = Column(Float, nullable=False, default=0)

   

    depot = relationship("Depot", back_populates="tarif_items")
    tarif = relationship("DepotTarif")
