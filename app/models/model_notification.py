# ✅ app/models/model_notification.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_parent_unread_created",
            "parent_user_id",
            "is_read",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String, nullable=False)
    message = Column(String, nullable=False)
    user_id = Column(Integer, nullable=True)  # sub-user ou null
    parent_user_id = Column(Integer, ForeignKey("users.id"))
    # models/model_notification.py (exemple)
    sub_user_id = Column(Integer, ForeignKey("sub_users.id"), nullable=True)
    sub_user_name = Column(String(100), nullable=True)
    sub_user_role = Column(String(100), nullable=True)

    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[parent_user_id])
