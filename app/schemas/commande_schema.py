from pydantic import BaseModel
from typing import List, Optional

class LigneCommandeVenteCreate(BaseModel):
    produit_id: int
    quantite: int
    unite_id: Optional[int] = None

class CommandeVenteCreate(BaseModel):
    client_id: int
    lignes: List[LigneCommandeVenteCreate]
    tva_appliquee: bool

class LigneCommandeAchatCreate(BaseModel):
    produit_id: int
    quantite: int

class CommandeAchatCreate(BaseModel):
    fournisseur_id: int
    lignes: List[LigneCommandeAchatCreate]
    tva_appliquee: bool