from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# 🧾 Schéma de création
class InterventionCreate(BaseModel):
    client_id: int
    employe_id: int
    description: str | None = None
    statut: str | None = "en cours"
    produits_ids: List[int] = []
    produit_ex: Optional[str] = None
    caracteristique_ex: Optional[str] = None
    commentaire_ex: Optional[str] = None


class InterventionOut(BaseModel):
    id: int
    client_id: int
    employe_id: int
    description: str | None
    statut: str
    date_intervention: datetime
    produits_ids: List[int]
    produit_ex: Optional[str] = None
    caracteristique_ex: Optional[str] = None
    commentaire_ex: Optional[str] = None


    class Config:
        from_attributes = True