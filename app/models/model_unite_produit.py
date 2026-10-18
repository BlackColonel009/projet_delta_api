from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class UniteProduit(Base):
    __tablename__ = "unites_produit"
    __table_args__ = (
        Index(
            "uq_unites_produit_enterprise_code_barre",
            "enterprise_id",
            "code_barre",
            unique=True,
            postgresql_where=text("code_barre IS NOT NULL AND enterprise_id IS NOT NULL"),
            sqlite_where=text("code_barre IS NOT NULL AND enterprise_id IS NOT NULL"),
        ),
        Index(
            "ix_unites_produit_enterprise_date",
            "enterprise_id",
            "date_creation",
        ),
        Index("ix_unites_produit_product_date", "produit_id", "date_creation"),
    )

    id = Column(Integer, primary_key=True, index=True)
    produit_id = Column(Integer, ForeignKey("produits.id", ondelete="CASCADE"), nullable=True)  # ← mettre True
    tracabilite = Column(String, unique=True, index=True, nullable=False)
    statut = Column(String, default="disponible")  # ex: disponible, vendu, réparé, supprimé
    date_creation = Column(DateTime, default=datetime.utcnow)
    code_barre = Column(String, index=True, nullable=True)
    date_modification = Column(DateTime, nullable=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    

    
    commande_vente_id = Column(Integer, ForeignKey("commandes_ventes.id"), nullable=True)
    commande_vente = relationship("CommandeVente", back_populates="unites_vendues")

    # Permet d'annuler proprement un achat sans toucher aux unités provenant
    # d'une autre commande.
    commande_achat_id = Column(
        Integer,
        ForeignKey("commandes_achats.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


    produit = relationship("Produit", back_populates="unites")
    


    def __repr__(self):
        return f"<UniteProduit {self.tracabilite} ({self.statut})>"
