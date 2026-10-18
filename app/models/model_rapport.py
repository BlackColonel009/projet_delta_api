# app/models/model_rapport.py
from sqlalchemy import Column, Integer, Text, Date, ForeignKey, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.model_user import User, SubUser
from sqlalchemy.ext.hybrid import hybrid_property

class Rapport(Base):
    __tablename__ = "rapports"
    __table_args__ = (
        Index("ix_rapports_enterprise_date", "enterprise_id", "date_creation"),
        UniqueConstraint(
            "enterprise_id", "source", "source_date",
            name="uq_rapports_enterprise_source_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    contenu = Column(Text, nullable=False)
    date_rapport = Column(Date, default=datetime.utcnow)
    date_creation = Column(DateTime, default=datetime.utcnow)
    date_modification = Column(DateTime, nullable=True)
    source = Column(String(32), nullable=False, default="manual")
    source_date = Column(Date, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=True, index=True)
    sub_user_id = Column(Integer, ForeignKey("sub_users.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", back_populates="rapports")
    sub_user = relationship("SubUser", back_populates="rapports")
    
    # @hybrid_property
    # def auteur(self):
    #     if self.user_id:
    #         return self.user.username or self.user.email
    #     elif self.sub_user:
    #         return self.sub_user.username
    #     return "Utilisateur"
