from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class PropertyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    property_type: Literal["building", "house", "apartment", "hotel", "commercial", "land", "other"]
    address: str = Field(min_length=3, max_length=500)
    description: str | None = Field(default=None, max_length=1000)


class PropertyUnitCreate(BaseModel):
    property_id: int
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    unit_type: Literal["room", "apartment", "house", "office", "shop", "space", "other"]
    rental_mode: Literal["short_term", "long_term", "mixed"] = "long_term"
    capacity: int = Field(default=1, ge=1)
    monthly_rate: float | None = Field(default=None, ge=0)
    nightly_rate: float | None = Field(default=None, ge=0)
    deposit_amount: float = Field(default=0, ge=0)


class OccupancyCreate(BaseModel):
    unit_id: int
    client_id: int
    occupancy_type: Literal["stay", "lease"]
    start_at: datetime
    end_at: datetime | None = None
    billing_day: int | None = Field(default=None, ge=1, le=28)

    @model_validator(mode="after")
    def validate_period(self):
        if self.occupancy_type == "stay" and self.end_at is None:
            raise ValueError("Une date de fin est requise pour un séjour")
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("La fin doit être postérieure au début")
        return self


class PropertyPaymentCreate(BaseModel):
    kind: Literal["rent", "deposit", "deposit_refund"]
    amount: float = Field(gt=0)
    due_id: int | None = None
    payment_method: str = Field(default="cash", min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=120)


class PropertyInspectionCreate(BaseModel):
    inspection_type: Literal["entry", "exit"]
    notes: str | None = Field(default=None, max_length=2000)
    condition: dict = Field(default_factory=dict)
    photos: list[str] = Field(default_factory=list, max_length=40)
    signed_by_client: bool = False


class PropertyMaintenanceCreate(BaseModel):
    property_id: int
    unit_id: int | None = None
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    estimated_cost: float = Field(default=0, ge=0)
    assigned_to: str | None = Field(default=None, max_length=160)


class PropertyMaintenanceUpdate(BaseModel):
    status: Literal["open", "planned", "in_progress", "completed", "cancelled"]
    actual_cost: float | None = Field(default=None, ge=0)


class PropertyReminderSettings(BaseModel):
    enabled: bool = True
    days_before: int = Field(default=3, ge=0, le=30)
    overdue_frequency_days: int = Field(default=3, ge=1, le=30)
    email_enabled: bool = False
