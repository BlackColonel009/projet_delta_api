from pydantic import BaseModel
from datetime import datetime
from typing import List

# 🧾 Schéma de création
class InterventionCreate(BaseModel):
    client_id: int
    employe_id: int
    description: str | None = None
    statut: str | None = "en cours"
    produits_ids: List[int] = []

class InterventionOut(BaseModel):
    id: int
    client_id: int
    employe_id: int
    description: str | None
    statut: str
    date_intervention: datetime
    produits_ids: List[int]

    class Config:
        from_attributes = True