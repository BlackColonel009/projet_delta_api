from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SubscriptionChangeRequest(Base):
    __tablename__ = "subscription_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    current_plan_code = Column(String(32), ForeignKey("subscription_plans.code"), nullable=True)
    requested_plan_code = Column(String(32), ForeignKey("subscription_plans.code"), nullable=False)
    billing_cycle = Column(String(16), nullable=False)
    quoted_amount = Column(Float, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="XOF")
    status = Column(String(16), nullable=False, default="pending", index=True)
    note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    requested_plan = relationship("SubscriptionPlan", foreign_keys=[requested_plan_code])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
