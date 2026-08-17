from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class DepotTarif(Base):
    __tablename__ = "depot_tarifs"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("depot_services.id"), nullable=False)
    nom_tarif = Column(String, nullable=False)
    mode_tarification = Column(String, nullable=False)  # 'duree' ou 'unitaire'
    tarif_unitaire = Column(Float, nullable=True)
    tarif_par_minute = Column(Float, nullable=True)
    actif = Column(Boolean, default=True)
    date_creation = Column(DateTime, default=datetime.utcnow)

    service = relationship("DepotService", backref="tarifs")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # <-- nouveau champ
    user = relationship("User", back_populates="depot_tarifs")


    def __repr__(self):
        return f"<DepotTarif {self.nom_tarif} - {self.mode_tarification}>"
    
    @property
    def service_nom(self):
        return self.service.nom if self.service else None
