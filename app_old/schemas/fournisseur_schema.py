from pydantic import BaseModel
from datetime import datetime

# 🧾 Schéma de création/modification
class FournisseurCreate(BaseModel):
    nom: str
    email: str | None = None
    telephone: str | None = None
    adresse: str | None = None
    type_fourniture: str | None = None

class FournisseurOut(FournisseurCreate):
    id: int
    date_creation: datetime

    class Config:
        from_attributes = True