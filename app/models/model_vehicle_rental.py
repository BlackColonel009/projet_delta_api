from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class RentalVehicle(Base):
    __tablename__ = "rental_vehicles"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "registration_number", name="uq_rental_vehicle_registration"),
        Index("ix_rental_vehicle_enterprise_status", "enterprise_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(160), nullable=False)
    category = Column(String(80), nullable=False)
    brand = Column(String(80), nullable=False)
    model = Column(String(80), nullable=False)
    year = Column(Integer)
    registration_number = Column(String(60), nullable=False)
    vin = Column(String(80))
    color = Column(String(50))
    mileage = Column(Float, nullable=False, default=0)
    fuel_level = Column(Float)
    daily_rate = Column(Float, nullable=False, default=0)
    hourly_rate = Column(Float)
    weekly_rate = Column(Float)
    deposit_amount = Column(Float, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="available")
    documents_json = Column(JSON, nullable=False, default=dict)
    photos_json = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class VehicleReservation(Base):
    __tablename__ = "vehicle_reservations"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "reservation_number", name="uq_vehicle_reservation_number"),
        Index("ix_vehicle_reservation_vehicle_dates", "vehicle_id", "start_at", "end_at"),
        Index("ix_vehicle_reservation_enterprise_status", "enterprise_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("rental_vehicles.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    reservation_number = Column(String(40), nullable=False)
    status = Column(String(32), nullable=False, default="reserved")
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    rate_snapshot = Column(Float, nullable=False)
    deposit_snapshot = Column(Float, nullable=False, default=0)
    estimated_total = Column(Float, nullable=False, default=0)
    paid_amount = Column(Float, nullable=False, default=0)
    deposit_paid = Column(Float, nullable=False, default=0)
    start_mileage = Column(Float)
    end_mileage = Column(Float)
    start_fuel_level = Column(Float)
    end_fuel_level = Column(Float)
    departure_notes = Column(String(1000))
    return_notes = Column(String(1000))
    inspection_json = Column(JSON, nullable=False, default=dict)
    created_by_name = Column(String(160), nullable=False)
    created_by_role = Column(String(60))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicle = relationship("RentalVehicle")
    client = relationship("Client")
    events = relationship("VehicleRentalEvent", back_populates="reservation", cascade="all, delete-orphan", order_by="VehicleRentalEvent.created_at")


class VehicleRentalEvent(Base):
    __tablename__ = "vehicle_rental_events"
    __table_args__ = (Index("ix_vehicle_rental_events_reservation_date", "reservation_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    reservation_id = Column(Integer, ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(32))
    to_status = Column(String(32), nullable=False)
    note = Column(String(500))
    agent_name = Column(String(160), nullable=False)
    agent_role = Column(String(60))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    reservation = relationship("VehicleReservation", back_populates="events")


class VehicleRentalPayment(Base):
    __tablename__ = "vehicle_rental_payments"
    __table_args__ = (Index("ix_vehicle_rental_payment_enterprise_date", "enterprise_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(24), nullable=False)  # rental, deposit, deposit_refund
    amount = Column(Float, nullable=False)
    payment_method = Column(String(40), nullable=False, default="cash")
    reference = Column(String(120))
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class VehicleRentalCharge(Base):
    __tablename__ = "vehicle_rental_charges"
    __table_args__ = (Index("ix_vehicle_rental_charge_reservation", "reservation_id"),)

    id = Column(Integer, primary_key=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("vehicle_reservations.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(32), nullable=False)  # late, damage, fuel, mileage, other
    label = Column(String(160), nullable=False)
    amount = Column(Float, nullable=False)
    notes = Column(String(500))
    agent_name = Column(String(160), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
