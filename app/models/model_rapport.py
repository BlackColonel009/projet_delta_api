# app/models/model_rapport.py
from sqlalchemy import Column, Integer, Text, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.models.model_user import User, SubUser
from sqlalchemy.ext.hybrid import hybrid_property

class Rapport(Base):
    __tablename__ = "rapports"

    id = Column(Integer, primary_key=True, index=True)
    contenu = Column(Text, nullable=False)
    date_rapport = Column(Date, default=datetime.utcnow)
    date_creation = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
