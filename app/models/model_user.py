from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy import DateTime
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_main_user = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)  # ✅ Nouvelle colonne
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    username = Column(String, nullable=True)
    societe_ou_entreprise = Column(String, nullable=True)
    account_type = Column(String, default="basic")
    created_at = Column(DateTime, default=datetime.utcnow)
    devise = Column(String, default="€")
    telephone = Column(String, nullable=True)
    logo_entreprise = Column(String, nullable=True)
    addresse = Column(String, nullable=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    sub_users = relationship("SubUser", back_populates="parent_user", cascade="all, delete")

    historiques = relationship("Historique", back_populates="user", overlaps="historiques_user")
    historiques_user = relationship("Historique", foreign_keys="[Historique.user_id]", overlaps="historiques")

    

    
class SubUser(Base):
    __tablename__ = "sub_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    telephone = Column(String, nullable=True)
    devise = Column(String(10), nullable=True)


    parent_user_id = Column(Integer, ForeignKey("users.id"))
    parent_user = relationship("User", back_populates="sub_users")

    historiques = relationship("Historique", back_populates="sub_user", overlaps="historiques_sub")
    historiques_sub = relationship("Historique", foreign_keys="[Historique.sub_user_id]", overlaps="historiques")



# ✅ À placer tout en bas du fichier, après les classes
from sqlalchemy.orm import relationship

User.rapports = relationship("Rapport", back_populates="user", lazy="dynamic")
SubUser.rapports = relationship("Rapport", back_populates="sub_user", lazy="dynamic")