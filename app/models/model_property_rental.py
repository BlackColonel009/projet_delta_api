from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class RentalProperty(Base):
    __tablename__ = "rental_properties"
    __table_args__ = (Index("ix_rental_property_enterprise_active", "enterprise_id", "is_active"),)
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(160), nullable=False)
    property_type = Column(String(40), nullable=False)
    address = Column(String(500), nullable=False)
    description = Column(String(1000))
    photos_json = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    units = relationship("PropertyUnit", back_populates="property", cascade="all, delete-orphan")


class PropertyUnit(Base):
    __tablename__ = "property_units"
    __table_args__ = (UniqueConstraint("property_id", "code", name="uq_property_unit_code"), Index("ix_property_unit_enterprise_status", "enterprise_id", "status"))
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    property_id = Column(Integer, ForeignKey("rental_properties.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(80), nullable=False)
    name = Column(String(160), nullable=False)
    unit_type = Column(String(40), nullable=False)
    rental_mode = Column(String(24), nullable=False, default="long_term")
    capacity = Column(Integer, nullable=False, default=1)
    monthly_rate = Column(Float)
    nightly_rate = Column(Float)
    deposit_amount = Column(Float, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="available")
    amenities_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    property = relationship("RentalProperty", back_populates="units")


class PropertyOccupancy(Base):
    __tablename__ = "property_occupancies"
    __table_args__ = (UniqueConstraint("enterprise_id", "contract_number", name="uq_property_contract_number"), Index("ix_property_occupancy_unit_dates", "unit_id", "start_at", "end_at"), Index("ix_property_occupancy_enterprise_status", "enterprise_id", "status"))
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("property_units.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    contract_number = Column(String(40), nullable=False)
    occupancy_type = Column(String(24), nullable=False)
    status = Column(String(32), nullable=False, default="reserved")
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime)
    rate_snapshot = Column(Float, nullable=False)
    deposit_snapshot = Column(Float, nullable=False, default=0)
    total_amount = Column(Float, nullable=False, default=0)
    paid_amount = Column(Float, nullable=False, default=0)
    deposit_held = Column(Float, nullable=False, default=0)
    billing_day = Column(Integer)
    created_by_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    unit = relationship("PropertyUnit")
    client = relationship("Client")
    dues = relationship("PropertyPaymentDue", back_populates="occupancy", cascade="all, delete-orphan")


class PropertyPaymentDue(Base):
    __tablename__ = "property_payment_dues"
    __table_args__ = (UniqueConstraint("occupancy_id", "due_date", name="uq_property_due_date"), Index("ix_property_due_enterprise_status_date", "enterprise_id", "status", "due_date"))
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    occupancy_id = Column(Integer, ForeignKey("property_occupancies.id", ondelete="CASCADE"), nullable=False)
    due_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    paid_amount = Column(Float, nullable=False, default=0)
    status = Column(String(24), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    occupancy = relationship("PropertyOccupancy", back_populates="dues")


class PropertyPayment(Base):
    __tablename__ = "property_payments"
    __table_args__ = (Index("ix_property_payment_enterprise_date", "enterprise_id", "created_at"),)
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    occupancy_id = Column(Integer, ForeignKey("property_occupancies.id", ondelete="CASCADE"), nullable=False)
    due_id = Column(Integer, ForeignKey("property_payment_dues.id", ondelete="SET NULL"))
    kind = Column(String(24), nullable=False)  # rent, deposit, deposit_refund
    amount = Column(Float, nullable=False)
    payment_method = Column(String(40), nullable=False, default="cash")
    reference = Column(String(120))
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PropertyInspection(Base):
    __tablename__ = "property_inspections"
    __table_args__ = (Index("ix_property_inspection_occupancy_date", "occupancy_id", "created_at"),)
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    occupancy_id = Column(Integer, ForeignKey("property_occupancies.id", ondelete="CASCADE"), nullable=False)
    inspection_type = Column(String(16), nullable=False)  # entry, exit
    notes = Column(String(2000))
    condition_json = Column(JSON, nullable=False, default=dict)
    photos_json = Column(JSON, nullable=False, default=list)
    signed_by_client = Column(Boolean, nullable=False, default=False)
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PropertyMaintenance(Base):
    __tablename__ = "property_maintenance"
    __table_args__ = (Index("ix_property_maintenance_enterprise_status", "enterprise_id", "status"),)
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    property_id = Column(Integer, ForeignKey("rental_properties.id", ondelete="CASCADE"), nullable=False)
    unit_id = Column(Integer, ForeignKey("property_units.id", ondelete="SET NULL"))
    title = Column(String(160), nullable=False)
    description = Column(String(1000))
    priority = Column(String(16), nullable=False, default="normal")
    status = Column(String(24), nullable=False, default="open")
    estimated_cost = Column(Float, nullable=False, default=0)
    actual_cost = Column(Float, nullable=False, default=0)
    assigned_to = Column(String(160))
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)


class PropertyReminderLog(Base):
    __tablename__ = "property_reminder_logs"
    __table_args__ = (
        UniqueConstraint("due_id", "channel", "reminder_key", name="uq_property_reminder_delivery"),
        Index("ix_property_reminder_enterprise_date", "enterprise_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    due_id = Column(Integer, ForeignKey("property_payment_dues.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(20), nullable=False)
    reminder_key = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="sent")
    error_message = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
