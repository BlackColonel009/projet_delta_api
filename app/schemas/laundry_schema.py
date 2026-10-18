from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


LaundryStatus = Literal[
    "received",
    "sorted",
    "processing",
    "drying",
    "ironing",
    "ready",
    "delivered",
    "cancelled",
    "incident",
]


class LaundryServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    pricing_mode: Literal["per_item", "per_kg", "flat"] = "per_item"
    unit_price: float = Field(ge=0)
    turnaround_minutes: int = Field(default=1440, ge=15, le=43200)


class LaundryServiceOut(LaundryServiceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool


class LaundryItemCreate(BaseModel):
    service_id: int
    category: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    quantity: int = Field(default=1, ge=1, le=10000)
    unit_price: float | None = Field(default=None, ge=0)
    condition_notes: str | None = Field(default=None, max_length=500)
    options: dict[str, Any] = Field(default_factory=dict)


class LaundryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    service_id: int
    category: str
    description: str | None
    quantity: int
    unit_price_snapshot: float
    line_total: float
    condition_notes: str | None
    options_json: dict[str, Any]
    status: str


class LaundryOrderCreate(BaseModel):
    client_id: int
    priority: Literal["normal", "express"] = "normal"
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    discount: float = Field(default=0, ge=0)
    items: list[LaundryItemCreate] = Field(min_length=1, max_length=200)


class LaundryTransition(BaseModel):
    status: LaundryStatus
    note: str | None = Field(default=None, max_length=500)


class LaundryPaymentCreate(BaseModel):
    amount: float = Field(gt=0)


class LaundryEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: str | None
    to_status: str
    note: str | None
    agent_name: str
    agent_role: str | None
    created_at: datetime


class LaundryOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    order_number: str
    status: str
    priority: str
    received_at: datetime
    due_at: datetime | None
    ready_at: datetime | None
    delivered_at: datetime | None
    notes: str | None
    subtotal: float
    discount: float
    total: float
    paid_amount: float
    created_by_name: str
    created_by_role: str | None
    items: list[LaundryItemOut] = Field(default_factory=list)
    events: list[LaundryEventOut] = Field(default_factory=list)
    client_name: str | None = None
