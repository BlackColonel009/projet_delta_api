# ✅ app/models/model_notification.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String, nullable=False)
    message = Column(String, nullable=False)
    user_id = Column(Integer, nullable=True)  # sub-user ou null
    parent_user_id = Column(Integer, ForeignKey("users.id"))
    # models/model_notification.py (exemple)
    sub_user_id = Column(Integer, ForeignKey("subusers.id"), nullable=True)
    sub_user_name = Column(String(100), nullable=True)
    sub_user_role = Column(String(100), nullable=True)

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[parent_user_id])