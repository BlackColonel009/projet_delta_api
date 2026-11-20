from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ClientProduitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    commande_id: Optional[int]
    produit_id: Optional[int]
    note: Optional[str]
    nom_produit: Optional[str]
    categorie_produit: Optional[str]
    prix_unitaire_backup: Optional[float]
    quantite: int
    prix_unitaire: float
    date_achat: datetime

