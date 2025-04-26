from pydantic import BaseModel
from datetime import datetime

class PaiementCreate(BaseModel):
    facture_id: int
    montant: float
    moyen_paiement: str = "espèces"
    devise: str = "FCFA"
