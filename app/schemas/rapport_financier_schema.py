from pydantic import BaseModel
from typing import List, Dict

class RapportMensuel(BaseModel):
    mois: str
    total: float

class RapportVentes(BaseModel):
    par_mois: List[RapportMensuel]
    total: float

class RapportAchats(BaseModel):
    par_mois: List[RapportMensuel]
    total: float

class RapportDepenses(BaseModel):
    par_mois: List[RapportMensuel]
    total: float

class RapportClients(BaseModel):
    nouveaux: int
    impayes: int

class RapportAnnuel(BaseModel):
    annee: int
    ventes: RapportVentes
    achats: RapportAchats
    depenses: RapportDepenses
    benefice_brut: float
    benefice_net: float
    clients: RapportClients
    stock_fin_annee: Dict[str, float]  # produit_id: quantite
