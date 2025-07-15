from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

# 🧾 Schéma de création (corrigé)
class InterventionCreate(BaseModel):
    client_id: int
    user_id: Optional[int] = None  # 🔧 présent dans le modèle mais manquant dans l'ancien schema
    description: Optional[str] = None
    statut: Optional[str] = "en cours"
    produits_ids: List[int] = []
    produit_ex: Optional[str] = None
    caracteristique_ex: Optional[str] = None
    commentaire_ex: Optional[str] = None


# 🔁 Schéma de réponse
class InterventionOut(BaseModel):
    id: int
    client_id: int
    user_id: int
    description: Optional[str]
    statut: str
    date_intervention: datetime
    produits_ids: List[int]
    produit_ex: Optional[str] = None
    caracteristique_ex: Optional[str] = None
    commentaire_ex: Optional[str] = None

    class Config:
        from_attributes = True
