from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
# 🧾 Schéma

class HistoriqueCreate(BaseModel):
    action: str
    type_entite: str
    entite_id: Optional[int] = None
    user_id: Optional[int] = None
    details: Optional[str] = None

class HistoriqueOut(HistoriqueCreate):
    id: int
    date_action: datetime

    class Config:
        from_attributes = True