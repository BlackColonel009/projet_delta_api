from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# 🧾 Schéma
class HistInterventionCreate(BaseModel):
    intervention_id: int
    produit_id: int
    user_id: Optional[int] = None
    action: Optional[str] = None

class HistInterventionOut(HistInterventionCreate):
    id: int
    date_action: datetime

    class Config:
        from_attributes = True
