from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class FactureDepotBase(BaseModel):
    montant_ht: float
    tva: Optional[float] = 0.0
    montant_ttc: float

    statut: Optional[str] = "en_attente"
    mode_paiement: Optional[str] = None
    date_paiement: Optional[datetime] = None
    remarques: Optional[str] = None


class FactureDepotCreate(FactureDepotBase):
    depot_id: int
    client_id: int


class FactureDepotUpdate(FactureDepotBase):
    pass


class FactureDepotOut(FactureDepotBase):
    id: int
    depot_id: int
    client_id: int
    date_facture: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
