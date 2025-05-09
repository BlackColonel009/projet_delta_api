# 📦 MODELE HISTORIQUE GENERAL SQLALCHEMY
# Fichier : app/models/model_historique.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import Session

class Historique(Base):
    __tablename__ = "historiques"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)  # Exemple: 'Ajout Produit', 'Suppression Vente'
    type_entite = Column(String, nullable=False)  # Exemple: 'produit', 'vente', 'intervention'
    entite_id = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(Text, nullable=True)  # description facultative ou JSON brut
    date_action = Column(DateTime, default=datetime.utcnow)
    sub_user_id = Column(Integer, ForeignKey("sub_users.id"), nullable=True)

    user = relationship("User", back_populates="historiques", overlaps="historiques_user")
    sub_user = relationship("SubUser", back_populates="historiques", overlaps="historiques_sub")
    def __repr__(self):
        return f"<Historique {self.action} sur {self.type_entite} #{self.entite_id}>"
