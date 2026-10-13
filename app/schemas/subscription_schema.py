from enum import Enum

from pydantic import BaseModel, Field, model_validator
from datetime import datetime

from app.models.model_souscription import SubscriptionType


class BillingCycle(str, Enum):
    free = "free"
    trial = "trial"
    monthly = "monthly"
    annual = "annual"


class GrantSubscriptionRequest(BaseModel):
    plan_code: str | None = Field(default=None, min_length=2, max_length=32)
    billing_cycle: BillingCycle | None = None
    # Compatibilite avec les anciennes versions mobiles deja en production.
    type: SubscriptionType | None = None

    @model_validator(mode="after")
    def validate_cycle(self):
        if self.billing_cycle is None and self.type is None:
            raise ValueError("billing_cycle is required")
        return self

    @property
    def resolved_cycle(self) -> BillingCycle:
        if self.billing_cycle is not None:
            return self.billing_cycle
        if self.type == SubscriptionType.yearly:
            return BillingCycle.annual
        return BillingCycle(self.type.value)


class SubscriptionCreate(BaseModel):
    user_id: int
    type: SubscriptionType
    end_date: datetime
