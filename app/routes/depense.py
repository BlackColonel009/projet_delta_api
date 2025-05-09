from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_depense import Depense
from app.schemas.depense_schema import DepenseCreate, DepenseOut
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action


router = APIRouter(prefix="/depenses", tags=["Dépenses"])

# ➕ Ajouter une dépense
@router.post("/", response_model=DepenseOut)
def create_depense(
    data: DepenseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    depense = Depense(**data.dict(), user_id=parent_user_id)  # 🔐 Liaison user
    db.add(depense)
    db.commit()
    db.refresh(depense)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout dépense",
        type_entite="depense",
        entite_id=depense.id,
        details=f"{depense.categorie}  ({depense.montant:.2f} €)"
    )

    
    return depense

# 📋 Lister toutes les dépenses de l'utilisateur
@router.get("/", response_model=List[DepenseOut])
def list_depenses(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):  
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    return db.query(Depense).filter(Depense.user_id == parent_user_id).order_by(Depense.date_depense.desc()).all()

# 📁 Filtrer les dépenses par catégorie
@router.get("/categorie/{categorie}", response_model=List[DepenseOut])
def list_depenses_par_categorie(
    categorie: str,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    depenses = (
        db.query(Depense)
        .filter(Depense.categorie == categorie, Depense.user_id == parent_user_id)
        .order_by(Depense.date_depense.desc())
        .all()
    )
    return depenses

# ❌ Supprimer une dépense
@router.delete("/{depense_id}")
def delete_depense(
    depense_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    depense = db.query(Depense).filter(
        Depense.id == depense_id,
        Depense.user_id == parent_user_id
    ).first()
    if not depense:
        raise HTTPException(status_code=404, detail="Dépense non trouvée")
    db.delete(depense)
    db.commit()
    
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression dépense",
        type_entite="depense",
        entite_id=depense.id,
        details=f"Dépense supprimée : {depense.libelle} ({depense.montant:.2f}€)"
    )

    
    return {"message": "Dépense supprimée avec succès"}
