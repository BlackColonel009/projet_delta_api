from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_fournisseur import Fournisseur
from app.schemas.fournisseur_schema import FournisseurCreate, FournisseurOut
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)


router = APIRouter(prefix="/fournisseurs", tags=["Fournisseurs"])

# ➕ Créer un fournisseur
@router.post("/", response_model=FournisseurOut)
def create_fournisseur(
    data: FournisseurCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    fournisseur = Fournisseur(
        **data.dict(),
        user_id=parent_user_id,
        enterprise_id=actor_enterprise_id(current_user),
    )
    db.add(fournisseur)
    db.commit()
    db.refresh(fournisseur)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout fournisseur",
        type_entite="fournisseur",
        entite_id=fournisseur.id,
        details=f"Fournisseur ajouté : {fournisseur.nom} ({fournisseur.telephone})"
    )

    
    return fournisseur

# 📋 Lister tous les fournisseurs
@router.get("/", response_model=List[FournisseurOut])
def list_fournisseurs(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    return db.query(Fournisseur).filter(
        enterprise_scope_filter(Fournisseur, current_user)
    ).all()

# 🔍 Voir un fournisseur par ID
@router.get("/{fournisseur_id}", response_model=FournisseurOut)
def get_fournisseur(
    fournisseur_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == fournisseur_id,
        enterprise_scope_filter(Fournisseur, current_user),
    ).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    return fournisseur

# 🔄 Modifier un fournisseur
@router.put("/{fournisseur_id}", response_model=FournisseurOut)
def update_fournisseur(
    fournisseur_id: int,
    data: FournisseurCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == fournisseur_id,
        enterprise_scope_filter(Fournisseur, current_user),
    ).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    for key, value in data.dict().items():
        setattr(fournisseur, key, value)
    db.commit()
    db.refresh(fournisseur)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Modification fournisseur",
        type_entite="fournisseur",
        entite_id=fournisseur.id,
        details=f"Fournisseur modifié : {fournisseur.nom}"
    )

    
    return fournisseur

# ❌ Supprimer un fournisseur
@router.delete("/{fournisseur_id}")
def delete_fournisseur(
    fournisseur_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    parent_user_id = actor_owner_id(current_user)
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == fournisseur_id,
        enterprise_scope_filter(Fournisseur, current_user),
    ).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    db.delete(fournisseur)
    db.commit()
    
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression fournisseur",
        type_entite="fournisseur",
        entite_id=fournisseur.id,
        details=f"Fournisseur supprimé : {fournisseur.nom}"
    )

    
    return {"message": "Fournisseur supprimé avec succès"}
