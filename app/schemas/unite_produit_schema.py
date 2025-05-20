# app/schemas/unite_produit_schema.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AddUnitesRequest(BaseModel):
    nombre: int
    prefixe: str = "TRAC-"

# Schéma pour création manuelle si besoin
class UniteProduitCreate(BaseModel):
    tracabilite: str

# Schéma pour affichage ou réponse API
class UniteProduitOut(BaseModel):
    id: int
    produit_id: Optional[int]
    tracabilite: str
    statut: str
    date_creation: datetime

    class Config:
        orm_mode = True