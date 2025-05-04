from pydantic import BaseModel
from typing import Optional

# 🎯 Schéma d'entrée attendu
class ScanQRInput(BaseModel):
    nom_produit: str
    tracabilite: str
    societe: Optional[str] = None

class ProduitCreateViaScan(BaseModel):
    nom: str
    categorie_id: int
    prix_achat: float
    prix_vente: float
    quantite: int
    couleur: Optional[str] = None
    commentaire: Optional[str] = None
    tracabilite: str
    societe: Optional[str] = None
    
class VenteTracabiliteInput(BaseModel):
    tracabilite: str
    quantite: int = 1
    client_id: Optional[int] = None
    tva_appliquee: Optional[bool] = False