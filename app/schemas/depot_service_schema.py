from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DepotServiceCreate(BaseModel):
    nom: str
    description: Optional[str]
    mode_tarification: str  # "duree" ou "unitaire"

class DepotServiceOut(BaseModel):
    id: int
    nom: str
    description: Optional[str]
    mode_tarification: str
    date_creation: datetime

    class Config:
        orm_mode = True
