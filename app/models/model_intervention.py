# 📦 MODELE INTERVENTION SQLALCHEMY
# Fichier : app/models/model_intervention.py

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

# Table de liaison produits/interventions
intervention_produits = Table(
    "intervention_produits",
    Base.metadata,
    Column("intervention_id", Integer, ForeignKey("interventions.id")),
    Column("produit_id", Integer, ForeignKey("produits.id"))
)

class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    employe_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # utilisateur principal (technicien)
    description = Column(Text, nullable=True)
    statut = Column(String, default="en cours")  # ex: en cours, terminé, annulé
    date_intervention = Column(DateTime, default=datetime.utcnow)

    # Relations
    client = relationship("Client", backref="interventions")
    employe = relationship("User", backref="interventions")
    produits = relationship("Produit", secondary=intervention_produits, backref="interventions")

    def __repr__(self):
        return f"<Intervention client={self.client_id} employe={self.employe_id}>"