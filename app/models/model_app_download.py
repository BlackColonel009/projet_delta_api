from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class AppDownloadSetting(Base):
    __tablename__ = "app_download_settings"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(16), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    download_url = Column(String(2048), nullable=True)
    version = Column(String(32), nullable=True)
    file_size_label = Column(String(40), nullable=True)
    sha256 = Column(String(64), nullable=True)
    release_notes = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
