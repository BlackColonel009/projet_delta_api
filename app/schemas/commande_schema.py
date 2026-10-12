from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class LigneCommandeVenteCreate(BaseModel):
    produit_id: int
    quantite: int = Field(gt=0)
    unite_id: Optional[int] = None
    codes: List[str] = Field(default_factory=list)
    prix_unitaire: Optional[float] = Field(default=None, ge=0)

class CommandeVenteCreate(BaseModel):
    client_id: int
    lignes: List[LigneCommandeVenteCreate] = Field(min_length=1)
    tva_appliquee: bool
    statut: str = "en_attente"


class LigneCommandeAchatCreate(BaseModel):
    produit_id: int
    quantite: int = Field(gt=0)
    prix_unitaire: Optional[float] = Field(default=None, ge=0)

class CommandeAchatCreate(BaseModel):
    fournisseur_id: int
    lignes: List[LigneCommandeAchatCreate] = Field(min_length=1)
    tva_appliquee: bool
    statut: str = "en_attente"


class LigneCommandeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produit_id: int
    nom_produit: str
    description: Optional[str] = None
    quantite: int
    prix_unitaire: float
    total_ligne: float


class CommandeVenteOut(BaseModel):
    id: int
    client_id: int
    date_commande: datetime
    total_ht: float
    total_ttc: float
    tva: float
    tva_appliquee: bool
    statut: str
    lignes: List[LigneCommandeOut]


class CommandeAchatOut(BaseModel):
    id: int
    fournisseur_id: int
    date_commande: datetime
    total_ht: float
    total_ttc: float
    tva: float
    tva_appliquee: bool
    statut: str
    lignes: List[LigneCommandeOut]
