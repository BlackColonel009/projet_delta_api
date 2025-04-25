from pydantic import BaseModel
from datetime import datetime


# 🧾 Schéma de création
class AchatCreate(BaseModel):
    produit_id: int
    fournisseur_id: int
    quantite: int
    prix_unitaire: float

class AchatOut(AchatCreate):
    id: int
    date_achat: datetime

    class Config:
        from_attributes = True