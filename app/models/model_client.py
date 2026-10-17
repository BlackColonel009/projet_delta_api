# 📦 MODELE CLIENT SQLALCHEMY
# Fichier : app/models/model_client.py

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    entreprise = Column(String, nullable=True)
    adresse = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)

    # Configuration du suivi apres paiement. Ces valeurs appartiennent au
    # client : deux clients d'une meme entreprise peuvent donc suivre des
    # parcours differents sans modifier les reglages globaux.
    followup_enabled = Column(Boolean, nullable=False, default=True)
    followup_thank_you_delay_days = Column(Integer, nullable=False, default=1)
    followup_recommendations_enabled = Column(
        Boolean, nullable=False, default=True
    )
    followup_first_recommendation_delay_days = Column(
        Integer, nullable=False, default=10
    )
    followup_recommendation_interval_days = Column(
        Integer, nullable=False, default=14
    )
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    user = relationship("User", backref="clients")
    commandes = relationship("CommandeVente", back_populates="client")
    factures = relationship("Facture", back_populates="client")
    produits_achetes = relationship("ClientProduit", back_populates="client", cascade="all, delete-orphan")
    # Dans Client
    followups = relationship("ClientFollowup", back_populates="client")

    depots = relationship("Depot", back_populates="client")


    def __repr__(self):
        return f"<Client {self.nom}>"
