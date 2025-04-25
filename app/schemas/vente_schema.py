from pydantic import BaseModel
from datetime import datetime


# 🧾 Schéma de création
class VenteCreate(BaseModel):
    produit_id: int
    client_id: int
    quantite: int

class VenteOut(VenteCreate):
    id: int
    prix_total: float
    date_vente: datetime

    class Config:
        from_attributes = True