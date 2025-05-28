from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class GaleriePhoto(Base):
    __tablename__ = "galerie_photos"

    id = Column(Integer, primary_key=True, index=True)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    image_url = Column(String, nullable=False)
    date_ajout = Column(DateTime, default=datetime.utcnow)

    produit = relationship("Produit", back_populates="galerie")
