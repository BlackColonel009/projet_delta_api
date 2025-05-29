from pydantic import BaseModel
from typing import List, Optional

class LigneCommandeVenteCreate(BaseModel):
    produit_id: int
    quantite: int
    unite_id: Optional[int] = None
    codes: List[str] = []  # ✅
    prix_unitaire: Optional[float] = None

class CommandeVenteCreate(BaseModel):
    client_id: int
    lignes: List[LigneCommandeVenteCreate]
    tva_appliquee: bool

class LigneCommandeAchatCreate(BaseModel):
    produit_id: int
    quantite: int
    prix_unitaire: Optional[float] = None

class CommandeAchatCreate(BaseModel):
    fournisseur_id: int
    lignes: List[LigneCommandeAchatCreate]
    tva_appliquee: bool