from sqlalchemy import Column, ForeignKey, Index, Integer, String, DateTime, func
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class DepotService(Base):
    __tablename__ = "depot_services"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    description = Column(String, nullable=True)
    mode_tarification = Column(String, nullable=False)  # 'duree' ou 'unitaire'
    date_creation = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # <-- nouveau champ
    user = relationship("User", back_populates="depot_services")

    __table_args__ = (
        Index(
            "uq_depot_service_company_name",
            user_id,
            func.lower(nom),
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<DepotService {self.nom}>"
