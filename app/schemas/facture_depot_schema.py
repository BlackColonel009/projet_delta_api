from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class FactureDepotCreate(BaseModel):
    depot_id: int
    remarques: Optional[str] = Field(default=None, max_length=1000)


class FactureDepotUpdate(BaseModel):
    remarques: Optional[str] = Field(default=None, max_length=1000)


class FactureDepotPaymentCreate(BaseModel):
    mode_paiement: str = Field(min_length=2, max_length=80)
    remarques: Optional[str] = Field(default=None, max_length=1000)


class FactureDepotOut(BaseModel):
    id: int
    depot_id: int
    client_id: int
    montant_ht: float
    tva: Optional[float] = 0.0
    montant_ttc: float
    statut: Optional[str] = "en_attente"
    mode_paiement: Optional[str] = None
    date_paiement: Optional[datetime] = None
    remarques: Optional[str] = None
    date_facture: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
