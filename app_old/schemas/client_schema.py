from pydantic import BaseModel, EmailStr
from typing import Optional

# 🧾 Schéma de création/modification
class ClientCreate(BaseModel):
    nom: str
    telephone: str | None = None
    email: str | None = None
    entreprise: str | None = None
    adresse: str | None = None

class ClientOut(ClientCreate):
    id: int

    class Config:
        from_attributes = True