from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_categorie import Categorie
from app.schemas.categorie_schema import CategorieOut, CategorieCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action


router = APIRouter(prefix="/categories", tags=["Catégories"])

# ➕ Créer une catégorie
@router.post("/", response_model=CategorieOut)
def create_categorie(
    data: CategorieCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    if db.query(Categorie).filter(Categorie.nom == data.nom, Categorie.user_id == current_user.id).first():
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    
    
    # 🔐 Liaison automatique à l'utilisateur connecté
    categorie = Categorie(**data.dict(), user_id=parent_user_id)
    db.add(categorie)
    db.commit()
    db.refresh(categorie)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout catégorie",
        type_entite="categorie",
        entite_id=categorie.id,
        details=f"Catégorie '{categorie.nom}' créée"
    )

    
    
    return categorie

# 📋 Lister toutes les catégories
@router.get("/", response_model=List[CategorieOut])
def list_categories(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock, RoleEnum.technicien]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    # 🔐 Ne lister que les catégories appartenant à l'utilisateur connecté
    return db.query(Categorie).filter(Categorie.user_id == parent_user_id).all()

# 🔍 Obtenir une catégorie par ID
@router.get("/{categorie_id}", response_model=CategorieOut)
def get_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    # 🔐 Accès uniquement à ses propres catégories
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == parent_user_id
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
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == parent_user_id 
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    
    for key, value in data.dict().items():
        setattr(categorie, key, value)
    
    
    log_action(
        db=db,
        current_user=current_user,
        action="Modification catégorie",
        type_entite="categorie",
        entite_id=categorie.id,
        details=f"Catégorie modifiée : {categorie.nom}"
    )

    
    
    db.commit()
    db.refresh(categorie)
    return categorie

# ❌ Supprimer une catégorie
@router.delete("/{categorie_id}")
def delete_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
    ):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        Categorie.user_id == parent_user_id 
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression catégorie",
        type_entite="categorie",
        entite_id=categorie.id,
        details=f"Catégorie supprimée : {categorie.nom}"
    )

    
    db.delete(categorie)
    db.commit()
    return {"message": "Catégorie supprimée avec succès"}
