# 📦 MODELE HISTORIQUE INTERVENTION SQLALCHEMY
# Fichier : app/models/model_historique_intervention.py

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class HistoriqueIntervention(Base):
    __tablename__ = "historiques_interventions"

    id = Column(Integer, primary_key=True, index=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("produits.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(Text, nullable=True)  # Exemple : "réparé", "diagnostiqué", "changé RAM"
    date_action = Column(DateTime, default=datetime.utcnow)
    sub_user_id = Column(Integer, ForeignKey("sub_users.id"), nullable=True)


    sub_user = relationship("SubUser", backref="historiques_interventions")
    intervention = relationship("Intervention", backref="historiques_interventions")
    produit = relationship("Produit", backref="historiques_interventions")
    user = relationship("User", backref="historiques_interventions")

    def __repr__(self):
        return f"<HistIntervention intervention={self.intervention_id} produit={self.produit_id}>"
