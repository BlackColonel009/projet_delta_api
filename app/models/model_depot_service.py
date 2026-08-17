from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class DepotService(Base):
    __tablename__ = "depot_services"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    mode_tarification = Column(String, nullable=False)  # 'duree' ou 'unitaire'
    date_creation = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # <-- nouveau champ
    user = relationship("User", back_populates="depot_services")

    def __repr__(self):
        return f"<DepotService {self.nom}>"
