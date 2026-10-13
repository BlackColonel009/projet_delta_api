from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text

from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    code = Column(String(32), primary_key=True)
    name = Column(String(80), nullable=False)
    description = Column(Text, nullable=False, default="")
    monthly_price = Column(Float, nullable=False, default=0)
    annual_price = Column(Float, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="XOF")
    max_sub_users = Column(Integer, nullable=True)
    max_products = Column(Integer, nullable=True)
    max_clients = Column(Integer, nullable=True)
    max_invoices_per_month = Column(Integer, nullable=True)
    features = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
