from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.model_facture import TypeFacture
from app.schemas.client_schema import ClientOut
from app.schemas.fournisseur_schema import FournisseurOut
from app.schemas.produit_schema import ProduitOut
from app.schemas.unite_produit_schema import UniteProduitOut
# 🧾 Schemas
class LigneFactureIn(BaseModel):
    produit_id: int
    description: str
    quantite: int = Field(gt=0)
    prix_unitaire: float = Field(ge=0)

class FactureCreate(BaseModel):
    type: TypeFacture
    client_id: Optional[int] = None
    fournisseur_id: Optional[int] = None
    remarques: Optional[str] = None
    tva: float = Field(default=0.0, ge=0, le=100)
    lignes: List[LigneFactureIn] = Field(min_length=1)
    devise: str = "FCFA"
    invoice_date: Optional[datetime] = None


class InvoiceOfficialDateUpdate(BaseModel):
    invoice_date: datetime


class InvoiceLineDisplayUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    caracteristiques: Dict[str, str] = Field(default_factory=dict)


# class LigneFactureOut(LigneFactureIn):
#     id: int
#     total_ligne: float
#     produit: Optional[dict]  # on garde produit simplifié (nom, caracs)
#     unites: List[UniteProduitOut]  # ⚠️ ajouté ici

class LigneFactureOut(BaseModel):
    id: int
    description: str
    quantite: int
    prix_unitaire: float
    total_ligne: float
    caracteristiques: Optional[Union[Dict[str, str], str]] = None
    produit: Optional[dict] = None  # nom + caracs
    unites: List[UniteProduitOut] = Field(default_factory=list)

    class Config:
        from_attributes = True

class FactureOut(BaseModel):
    id: int
    type: TypeFacture
    client_id: Optional[int]
    client: Optional[ClientOut] = None
    fournisseur_id: Optional[int]
    fournisseur: Optional[FournisseurOut] = None
    date_creation: datetime
    statut: str
    remarques: Optional[str]
    total_ht: float
    total_ttc: float
    total_paye: float
    technical_created_at: Optional[datetime] = None
    issuer_name_snapshot: Optional[str] = None
    issuer_role_snapshot: Optional[str] = None
    invoice_color_snapshot: Optional[str] = None
    simple_template_snapshot: Optional[str] = None
    professional_template_snapshot: Optional[str] = None
    tva: float
    lignes: List[LigneFactureOut]
    total_paye: float
    

    class Config:
        from_attributes = True
