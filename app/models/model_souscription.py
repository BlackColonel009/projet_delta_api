from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from enum import Enum

class SubscriptionType(str, Enum):
    trial = "trial"
    monthly = "monthly"
    yearly = "yearly"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)  
    # trial | monthly | yearly

    status = Column(String, default="active")  
    # active | expired | suspended

    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)

    granted_by_admin = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")
