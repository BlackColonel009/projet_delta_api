from fastapi import APIRouter, Depends, HTTPException, Body, File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.model_produit import Produit
from app.schemas.produit_schema import ProduitCreate, ProduitOut
from pydantic import BaseModel
from datetime import datetime
from app.utils.logger import log_action
from app.utils.security import get_current_user
from app.models.model_user import User
import shutil
import os


router = APIRouter(prefix="/produits", tags=["Produits"])

# ➕ Créer un produit
# ➕ Créer un produit avec image (multipart)
@router.post("/", response_model=dict)
def create_produit(
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
    tracabilite: Optional[str] = Form(None),
    emplacement: Optional[str] = Form("magasin"),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    # Enregistrement de l'image sur disque
    ext = image.filename.split(".")[-1]
    image_filename = f"{datetime.utcnow().timestamp()}.{ext}"
    image_path = os.path.join("upload", "produits", image_filename)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    produit = Produit(
        nom=nom,
        categorie_id=categorie_id,
        prix_achat=prix_achat,
        prix_vente=prix_vente,
        fournisseur_id=fournisseur_id,
        quantite=quantite,
        rating=rating,
        caracteristiques=caracteristiques,
        couleur=couleur,
        etat=etat,
        commentaire=commentaire,
        is_installe=is_installe,
        tracabilite=tracabilite,
        emplacement=emplacement,
        image_url=f"/static/produits/{image_filename}"
    )

    db.add(produit)
    db.commit()
    db.refresh(produit)

    log_action(
        db=db,
        user_id=current_user.id,
        action="Ajout Produit",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit: {produit.nom}, Quantité: {produit.quantite}"
    )

    return {"message": "Produit créé avec succès", "produit_id": produit.id}


# 📋 Lister tous les produits
@router.get("/", response_model=List[ProduitOut])
def list_produits(db: Session = Depends(get_db)):
    return db.query(Produit).filter(Produit.date_suppression == None).all()

# 🔍 Voir un produit par ID
@router.get("/{produit_id}", response_model=ProduitOut)
def get_produit(produit_id: int, db: Session = Depends(get_db)):
    produit = db.query(Produit).filter(Produit.id == produit_id, Produit.date_suppression == None).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    return produit

# 🔄 Modifier un produit
@router.put("/{produit_id}/", response_model=dict)
def update_produit(
    produit_id: int,
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
    tracabilite: Optional[str] = Form(None),
    emplacement: Optional[str] = Form("magasin"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # Gérer l'image si fournie
    if image:
        if produit.image_url:
            old_path = produit.image_url.replace("/static", "upload")
            if os.path.exists(old_path):
                os.remove(old_path)

        ext = image.filename.split(".")[-1]
        image_filename = f"{datetime.utcnow().timestamp()}.{ext}"
        image_path = os.path.join("upload", "produits", image_filename)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        produit.image_url = f"/static/produits/{image_filename}"

    # Mise à jour des champs
    produit.nom = nom
    produit.categorie_id = categorie_id
    produit.prix_achat = prix_achat
    produit.prix_vente = prix_vente
    produit.fournisseur_id = fournisseur_id
    produit.quantite = quantite
    produit.rating = rating
    produit.caracteristiques = caracteristiques
    produit.couleur = couleur
    produit.etat = etat
    produit.commentaire = commentaire
    produit.is_installe = is_installe
    produit.tracabilite = tracabilite
    produit.emplacement = emplacement
    produit.date_modification = datetime.utcnow()

    db.commit()

    log_action(
        db=db,
        user_id=current_user.id,
        action="Modification Produit",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit de nom: {produit.nom} mis à jour (avec ou sans image)"
    )

    return {"message": "Produit modifié avec succès."}

# ❌ Suppression logique d'un produit
@router.delete("/{produit_id}")
def delete_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    ):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    produit.date_suppression = datetime.utcnow()
    db.commit()
    
    log_action(
        db=db,
        user_id=current_user.id,
        action=" Produit supprimé!",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit au nom: {produit.nom} à été supprimé"
    )
    return {"message": "Produit supprimé (logiquement)"}

# 📋 Voir les produits supprimés (soft delete)
@router.get("/supprimes", response_model=List[ProduitOut])
def list_deleted_produits(db: Session = Depends(get_db)):
    return db.query(Produit).filter(Produit.date_suppression.isnot(None)).all()
