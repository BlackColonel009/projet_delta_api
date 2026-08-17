# Exemple de modèle ClientProduit enrichi avec backup d'infos produit
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class ClientProduit(Base):
    __tablename__ = "client_produits"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"))
    commande_id = Column(Integer, ForeignKey("commandes_ventes.id", ondelete="SET NULL"))
    produit_id = Column(Integer, ForeignKey("produits.id", ondelete="SET NULL"))
    note = Column(String, nullable=True)
    
    # 🧠 Backup des infos produit pour traçabilité
    nom_produit = Column(String, nullable=True)
    categorie_produit = Column(String, nullable=True)
    prix_unitaire_backup = Column(Float, nullable=True)

    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    date_achat = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="produits_achetes")
    commande = relationship("CommandeVente")
    produit = relationship("Produit")

    date_modification = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
