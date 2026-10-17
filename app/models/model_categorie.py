# 📦 MODELE CATEGORIE SQLALCHEMY
# Fichier : app/models/model_categorie.py

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Index, text
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

class Categorie(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index(
            "uq_categories_enterprise_name",
            "enterprise_id",
            text("lower(nom)"),
            unique=True,
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    description = Column(String, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    user = relationship("User", backref="categories")
    def __repr__(self):
        return f"<Categorie {self.nom}>"
