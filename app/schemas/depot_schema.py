from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

from enum import Enum



class MessageResponse(BaseModel):
    message: str


class TarifItemCreate(BaseModel):
    tarif_id: int
    quantite: int = Field(default=1, ge=1, le=100000)
    prix_personnalise: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None

class TarifItemOut(BaseModel):
    tarif_id: int
    quantite: int
    prix_personnalise: Optional[float]
    description: Optional[str] = None
    mode_tarification_snapshot: Optional[str] = None
    prix_unitaire_snapshot: Optional[float] = None
    montant_total: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class DepotStatutEnum(str, Enum):
    en_attente = "en_attente"
    recu = "recu"
    stocke = "stocke"
    pret_retrait = "pret_retrait"
    retire = "retire"
    annule = "annule"
    facture_creee = "facture_creee"
    facture = "facture"
    paye = "paye"


class DepotCancellation(BaseModel):
    motif: str = Field(min_length=3, max_length=500)


class DepotRestore(BaseModel):
    motif: Optional[str] = Field(default=None, max_length=500)

class DepotCreate(BaseModel):
    client_id: int
    service_id: int
    description_bien: str = Field(min_length=2, max_length=500)
    tarif_items: List[TarifItemCreate] = Field(min_length=1)

class DepotOut(BaseModel):
    id: int
    client_id: int
    client_nom: Optional[str] = None 
    service_id: int
    description_bien: str
    date_depot: datetime
    date_stockage: Optional[datetime] = None
    date_pret_retrait: Optional[datetime] = None
    date_retrait: Optional[datetime]
    date_annulation: Optional[datetime] = None
    motif_annulation: Optional[str] = None
    statut_modifie_le: Optional[datetime] = None
    statut_modifie_par: Optional[int] = None
    statut: DepotStatutEnum
    duree_minutes: Optional[int]
    prix_total: Optional[float]
    tarif_items: List[TarifItemOut]
    facture_id: Optional[int] = None
    facture_depot_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
