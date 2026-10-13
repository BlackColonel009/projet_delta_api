from enum import Enum

from pydantic import BaseModel, Field


class RequestBillingCycle(str, Enum):
    monthly = "monthly"
    annual = "annual"


class SubscriptionChangeRequestCreate(BaseModel):
    plan_code: str = Field(min_length=2, max_length=32)
    billing_cycle: RequestBillingCycle
    note: str | None = Field(default=None, max_length=500)


class SubscriptionChangeRequestReview(BaseModel):
    admin_note: str | None = Field(default=None, max_length=500)
