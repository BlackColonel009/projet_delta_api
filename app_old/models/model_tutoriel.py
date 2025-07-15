from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Tutoriel(Base):
    __tablename__ = "tutoriels"

    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    navigation = Column(Text, nullable=True)
    image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
