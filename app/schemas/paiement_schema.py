from pydantic import BaseModel, Field
from datetime import datetime

class PaiementCreate(BaseModel):
    facture_id: int
    montant: float = Field(gt=0)
    moyen_paiement: str = Field(default="espèces", min_length=1, max_length=64)
    devise: str = Field(default="FCFA", min_length=1, max_length=10)
    # commande_id: int | None = None
