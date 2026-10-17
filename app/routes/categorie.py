from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_categorie import Categorie
from app.schemas.categorie_schema import CategorieOut, CategorieCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)


router = APIRouter(prefix="/categories", tags=["Catégories"])

# ➕ Créer une catégorie
@router.post("/", response_model=CategorieOut)
def create_categorie(
    data: CategorieCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
    
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    if db.query(Categorie).filter(
        Categorie.nom == data.nom,
        enterprise_scope_filter(Categorie, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    
    
    # 🔐 Liaison automatique à l'utilisateur connecté
    categorie = Categorie(
        **data.dict(),
        user_id=parent_user_id,
        enterprise_id=enterprise_id,
    )
    db.add(categorie)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cette catégorie existe déjà.",
        )
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
    parent_user_id = actor_owner_id(current_user)
    # 🔐 Ne lister que les catégories appartenant à l'utilisateur connecté
    return db.query(Categorie).filter(
        enterprise_scope_filter(Categorie, current_user)
    ).all()

# 🔍 Obtenir une catégorie par ID
@router.get("/{categorie_id}", response_model=CategorieOut)
def get_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    # 🔐 Accès uniquement à ses propres catégories
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        enterprise_scope_filter(Categorie, current_user),
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
    parent_user_id = actor_owner_id(current_user)
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        enterprise_scope_filter(Categorie, current_user),
    ).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")

    duplicate = db.query(Categorie).filter(
        Categorie.nom == data.nom,
        enterprise_scope_filter(Categorie, current_user),
        Categorie.id != categorie_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    
    for key, value in data.dict().items():
        setattr(categorie, key, value)
    
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cette catégorie existe déjà.",
        )
    db.refresh(categorie)

    log_action(
        db=db,
        current_user=current_user,
        action="Modification catégorie",
        type_entite="categorie",
        entite_id=categorie.id,
        details=f"Catégorie modifiée : {categorie.nom}"
    )

    return categorie

# ❌ Supprimer une catégorie
@router.delete("/{categorie_id}")
def delete_categorie(
    categorie_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
    ):
    parent_user_id = actor_owner_id(current_user)
    categorie = db.query(Categorie).filter(
        Categorie.id == categorie_id,
        enterprise_scope_filter(Categorie, current_user),
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
