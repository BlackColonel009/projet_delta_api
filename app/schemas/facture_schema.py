from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.model_facture import TypeFacture
from app.schemas.client_schema import ClientOut
# 🧾 Schemas
class LigneFactureIn(BaseModel):
    produit_id: int
    description: str
    quantite: int
    prix_unitaire: float

class FactureCreate(BaseModel):
    type: TypeFacture
    client_id: Optional[int] = None
    fournisseur_id: Optional[int] = None
    remarques: Optional[str] = None
    tva: float = 0.0
    lignes: List[LigneFactureIn]
    devise: str = "FCFA"


class LigneFactureOut(LigneFactureIn):
    id: int
    total_ligne: float

    class Config:
        from_attributes = True

class FactureOut(BaseModel):
    id: int
    type: TypeFacture
    client_id: Optional[int]
    client: Optional[ClientOut]
    fournisseur_id: Optional[int]
    date_creation: datetime
    statut: str
    remarques: Optional[str]
    total_ht: float
    total_ttc: float
    total_paye: float
    tva: float
    lignes: List[LigneFactureOut]
    total_paye: float

    class Config:
        from_attributes = True