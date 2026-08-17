from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DepotTarifCreate(BaseModel):
    service_id: int
    nom_tarif: str
    mode_tarification: str  # "duree" ou "unitaire"
    tarif_unitaire: Optional[float] = None
    tarif_par_minute: Optional[float] = None
    actif: Optional[bool] = True

    

class DepotTarifOut(BaseModel):
    id: int
    nom_tarif: str
    mode_tarification: str
    tarif_unitaire: Optional[float]
    tarif_par_minute: Optional[float]
    service_id: int
    actif: bool
    date_creation: datetime
    service_nom: str


    class Config:
        orm_mode = True
