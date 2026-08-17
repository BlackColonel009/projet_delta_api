from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from enum import Enum



class MessageResponse(BaseModel):
    message: str


class TarifItemCreate(BaseModel):
    tarif_id: int
    quantite: int = 1
    prix_personnalise: Optional[float] = None
    description: Optional[str] = None

class TarifItemOut(BaseModel):
    tarif_id: int
    quantite: int
    prix_personnalise: Optional[float]
    description: Optional[str] = None

    class Config:
        orm_mode = True

class DepotStatutEnum(str, Enum):
    en_attente = "en_attente"
    retire = "retire"
    annule = "annule"
    facture_creee = "facture_creee"

class DepotCreate(BaseModel):
    client_id: int
    service_id: int
    description_bien: str
    tarif_items: List[TarifItemCreate] = []

class DepotOut(BaseModel):
    id: int
    client_id: int
    client_nom: Optional[str] = None 
    service_id: int
    description_bien: str
    date_depot: datetime
    date_retrait: Optional[datetime]
    statut: DepotStatutEnum
    duree_minutes: Optional[int]
    prix_total: Optional[float]
    tarif_items: List[TarifItemOut]
    facture_id: Optional[int] = None
    facture_depot_id: Optional[int] = None

    class Config:
        orm_mode = True
