from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class DepenseCreate(BaseModel):
    libelle: str
    montant: float
    categorie: Literal["Loyer", "Internet", "Transport", "Salaires", "Divers"] = "Divers"

class DepenseOut(DepenseCreate):
    id: int
    date_depense: datetime

    class Config:
        orm_mode = True
