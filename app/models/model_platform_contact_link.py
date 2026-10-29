from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class PlatformContactLink(Base):
    __tablename__ = "platform_contact_links"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(80), nullable=False)
    icon_key = Column(String(24), nullable=False, default="other")
    url = Column(String(2048), nullable=False)
    is_visible = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
