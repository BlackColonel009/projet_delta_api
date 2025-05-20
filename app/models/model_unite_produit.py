from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class UniteProduit(Base):
    __tablename__ = "unites_produit"

    id = Column(Integer, primary_key=True, index=True)
    produit_id = Column(Integer, ForeignKey("produits.id", ondelete="CASCADE"), nullable=True)  # ← mettre True
    tracabilite = Column(String, unique=True, index=True, nullable=False)
    statut = Column(String, default="disponible")  # ex: disponible, vendu, réparé, supprimé
    date_creation = Column(DateTime, default=datetime.utcnow)
    code_barre = Column(String, unique=True, index=True, nullable=True)
    
    produit = relationship("Produit", back_populates="unites")
    


    def __repr__(self):
        return f"<UniteProduit {self.tracabilite} ({self.statut})>"
