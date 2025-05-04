from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_categorie import Categorie
from app.schemas.categorie_schema import CategorieOut, CategorieCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router = APIRouter(prefix="/categories", tags=["Catégories"])

# ➕ Créer une catégorie
@router.post("/", response_model=CategorieOut)
def create_categorie(
    data: CategorieCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"])),
):
    if db.query(Categorie).filter(Categorie.nom == data.nom, Categorie.user_id == current_user.id).first():
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    
    # 🔐 Liaison automatique à l'utilisateur connecté
    categorie = Categorie(**data.dict(), user_id=current_user.id)
    db.add(categorie)
    db.commit()
    db.refresh(categorie)
    return categorie

# 📋 Lister toutes les catégories
@router.get("/", response_model=List[CategorieOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"]))
):
    # 🔐 Ne lister que les catégories appartenant à l'utilisateur connecté
    return db.query(Categorie).filter(Categorie.user_id == current_user.id).all()

# 🔍 Obtenir une catégorie par ID
@router.get("/{categorie_id}", response_model=CategorieOut)
def get_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"])),
):
    # 🔐 Accès uniquement à ses propres catégories
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == current_user.id
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    return categorie

# 🔄 Modifier une catégorie
@router.put("/{categorie_id}", response_model=CategorieOut)
def update_categorie(
    categorie_id: int,
    data: CategorieCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"])),
):
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == current_user.id
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    
    for key, value in data.dict().items():
        setattr(categorie, key, value)
    
    db.commit()
    db.refresh(categorie)
    return categorie

# ❌ Supprimer une catégorie
@router.delete("/{categorie_id}")
def delete_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"])),
):
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == current_user.id
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    
    db.delete(categorie)
    db.commit()
    return {"message": "Catégorie supprimée avec succès"}
