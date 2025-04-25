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
    account_type = Column(String, default="basic")
    created_at = Column(DateTime, default=datetime.utcnow)

    sub_users = relationship("SubUser", back_populates="parent_user", cascade="all, delete")

class SubUser(Base):
    __tablename__ = "sub_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    parent_user_id = Column(Integer, ForeignKey("users.id"))
    parent_user = relationship("User", back_populates="sub_users")
