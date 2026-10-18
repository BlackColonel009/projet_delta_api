from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VehicleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    year: int | None = Field(default=None, ge=1900, le=2200)
    registration_number: str = Field(min_length=2, max_length=60)
    vin: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=50)
    mileage: float = Field(default=0, ge=0)
    fuel_level: float | None = Field(default=None, ge=0, le=100)
    daily_rate: float = Field(ge=0)
    hourly_rate: float | None = Field(default=None, ge=0)
    weekly_rate: float | None = Field(default=None, ge=0)
    deposit_amount: float = Field(default=0, ge=0)


class VehicleOut(VehicleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    is_active: bool


class ReservationCreate(BaseModel):
    vehicle_id: int
    client_id: int
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_at <= self.start_at:
            raise ValueError("La fin doit être postérieure au début")
        return self


class ReservationTransition(BaseModel):
    status: Literal["confirmed", "prepared", "rented", "return_expected", "inspection", "completed", "cancelled", "late", "damaged"]
    mileage: float | None = Field(default=None, ge=0)
    fuel_level: float | None = Field(default=None, ge=0, le=100)
    note: str | None = Field(default=None, max_length=500)
    inspection: dict[str, Any] = Field(default_factory=dict)


class RentalPaymentCreate(BaseModel):
    kind: Literal["rental", "deposit", "deposit_refund"]
    amount: float = Field(gt=0)
    payment_method: str = Field(default="cash", min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=120)


class RentalChargeCreate(BaseModel):
    kind: Literal["late", "damage", "fuel", "mileage", "other"]
    label: str = Field(min_length=2, max_length=160)
    amount: float = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehicle_id: int
    client_id: int
    reservation_number: str
    status: str
    start_at: datetime
    end_at: datetime
    rate_snapshot: float
    deposit_snapshot: float
    estimated_total: float
    paid_amount: float
    deposit_paid: float
    created_by_name: str
    vehicle_name: str | None = None
    client_name: str | None = None
