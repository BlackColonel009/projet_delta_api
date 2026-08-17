from pydantic import BaseModel
from datetime import datetime

from app.models.model_souscription import SubscriptionType

class GrantSubscriptionRequest(BaseModel):
    type: SubscriptionType


class SubscriptionCreate(BaseModel):
    user_id: int
    type: SubscriptionType
    end_date: datetime
