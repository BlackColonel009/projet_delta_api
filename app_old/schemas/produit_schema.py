from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from fastapi import Form
from app.schemas.categorie_schema import CategorieOut
# 🧾 Schéma de création / mise à jour


class ProduitCreate:
    def __init__(
        self,
        nom: str = Form(...),
        categorie_id: int = Form(...),
        prix_achat: float = Form(...),
        prix_vente: float = Form(...),
        fournisseur_id: Optional[int] = Form(None),
        quantite: int = Form(...),
        rating: Optional[float] = Form(None),
        caracteristiques: Optional[str] = Form(None),
        couleur: Optional[str] = Form(None),
        etat: Optional[str] = Form("oui"),
        commentaire: Optional[str] = Form(None),
        is_installe: Optional[bool] = Form(False),
        # tracabilite: Optional[str] = Form(None),
        emplacement: Optional[str] = Form("magasin"),
        scanned_barcodes: Optional[List[str]] = Form(None),  # ✅ correction ici
    ):
        self.nom = nom
        self.categorie_id = categorie_id
        self.prix_achat = prix_achat
        self.prix_vente = prix_vente
        self.fournisseur_id = fournisseur_id
        self.quantite = quantite
        self.rating = rating
        self.caracteristiques = caracteristiques
        self.couleur = couleur
        self.etat = etat
        self.commentaire = commentaire
        self.is_installe = is_installe
        # self.tracabilite = tracabilite
        self.emplacement = emplacement
        self.scanned_barcodes = scanned_barcodes or []  # ✅ pour éviter None


class ProduitOut(BaseModel):
    id: int
    nom: str
    categorie_id: int
    categorie: Optional[CategorieOut]  # <--- pour récupérer nom, etc.
    prix_achat: float
    prix_vente: float
    fournisseur_id: Optional[int]
    quantite: int
    rating: Optional[float]
    caracteristiques: Optional[str]
    couleur: Optional[str]
    etat: Optional[str]
    commentaire: Optional[str]
    is_installe: Optional[bool]
    # tracabilite: Optional[str]
    emplacement: Optional[str]
    image_url: Optional[str]
    date_creation: datetime
    date_modification: datetime

    class Config:
        from_attributes = True