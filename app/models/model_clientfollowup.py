from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
from app.database import Base  # adapte selon ton projet

class FollowupStatus(PyEnum):
    en_attente = "en_attente"
    message_1_envoye = "message_1_envoye"
    message_2_envoye = "message_2_envoye"
    termine = "termine"
    fidelisation = "fidélisation"
    desactive = "désactiver"

class ClientFollowup(Base):
    __tablename__ = "client_followup"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)  # adapte le nom de la table client
    commande_id = Column(Integer, ForeignKey("commandes_ventes.id"), nullable=False)    # adapte le nom de la table commande
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 
    date_achat = Column(DateTime, default=datetime.utcnow)
    statut = Column(Enum(FollowupStatus), default=FollowupStatus.en_attente)
    date_prochain_envoi = Column(DateTime, nullable=True)
    
    # ⏳ délai avant première relance (configurable depuis le frontend)
    delai_avant_relance = Column(Integer, default=2)

    # 🧠 anti-harcèlement (trace du dernier envoi)
    dernier_envoi = Column(DateTime, nullable=True)

    type_followup = Column(String, nullable=False, default="fidélisation")

    client = relationship("Client", back_populates="followups")
    commandes = relationship("CommandeVente", back_populates="followups")
    
