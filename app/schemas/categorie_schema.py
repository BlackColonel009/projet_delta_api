from pydantic import BaseModel
from datetime import datetime

# 🧾 Schéma de création/modification
class CategorieCreate(BaseModel):
    nom: str
    description: str | None = None

class CategorieOut(CategorieCreate):
    id: int
    nom: str
    date_creation: datetime
    user_id: int

    class Config:
        from_attributes = True
        