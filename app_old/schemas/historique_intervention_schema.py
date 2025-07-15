from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MiniUser(BaseModel):
    id: int
    email: str
    class Config:
        from_attributes = True

class MiniSubUser(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        from_attributes = True

# 🧾 Schéma
class HistInterventionCreate(BaseModel):
    intervention_id: int
    produit_id: int
    user_id: Optional[int] = None
    action: Optional[str] = None

class HistInterventionOut(HistInterventionCreate):
    id: int
    date_action: datetime
    user: Optional[MiniUser] = None
    sub_user: Optional[MiniSubUser] = None

    class Config:
        from_attributes = True
