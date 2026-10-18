from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LaundryService(Base):
    __tablename__ = "laundry_services"
    __table_args__ = (
        UniqueConstraint(
            "enterprise_id",
            "name",
            name="uq_laundry_services_enterprise_name",
        ),
        Index("ix_laundry_services_enterprise_active", "enterprise_id", "is_active"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    pricing_mode = Column(String(24), nullable=False, default="per_item")
    unit_price = Column(Float, nullable=False, default=0)
    turnaround_minutes = Column(Integer, nullable=False, default=1440)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LaundryOrder(Base):
    __tablename__ = "laundry_orders"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "order_number", name="uq_laundry_orders_number"),
        Index("ix_laundry_orders_enterprise_status", "enterprise_id", "status"),
        Index("ix_laundry_orders_enterprise_received", "enterprise_id", "received_at"),
        Index("ix_laundry_orders_enterprise_due", "enterprise_id", "due_at"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    order_number = Column(String(40), nullable=False)
    status = Column(String(32), nullable=False, default="received")
    priority = Column(String(16), nullable=False, default="normal")
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=True)
    ready_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    notes = Column(String(1000), nullable=True)
    subtotal = Column(Float, nullable=False, default=0)
    discount = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)
    paid_amount = Column(Float, nullable=False, default=0)
    created_by_name = Column(String(160), nullable=False)
    created_by_role = Column(String(60), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client")
    items = relationship(
        "LaundryItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="LaundryItem.id",
    )
    events = relationship(
        "LaundryOrderEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="LaundryOrderEvent.created_at",
    )


class LaundryItem(Base):
    __tablename__ = "laundry_items"
    __table_args__ = (Index("ix_laundry_items_order", "order_id"),)

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("laundry_orders.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("laundry_services.id"), nullable=False)
    category = Column(String(80), nullable=False)
    description = Column(String(300), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_snapshot = Column(Float, nullable=False)
    line_total = Column(Float, nullable=False)
    condition_notes = Column(String(500), nullable=True)
    options_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="received")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("LaundryOrder", back_populates="items")
    service = relationship("LaundryService")


class LaundryOrderEvent(Base):
    __tablename__ = "laundry_order_events"
    __table_args__ = (Index("ix_laundry_events_order_date", "order_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("laundry_orders.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    note = Column(String(500), nullable=True)
    agent_name = Column(String(160), nullable=False)
    agent_role = Column(String(60), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("LaundryOrder", back_populates="events")


class LaundryPayment(Base):
    __tablename__ = "laundry_payments"
    __table_args__ = (
        Index("ix_laundry_payments_enterprise_date", "enterprise_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, ForeignKey("laundry_orders.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(40), nullable=False, default="cash")
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
