from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_depot_service import DepotService
from app.schemas.depot_service_schema import DepotServiceCreate, DepotServiceOut
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action

router = APIRouter(prefix="/depot-services", tags=["Dépôt - Services"])

# ➕ Créer un service de dépôt
@router.post("/", response_model=DepotServiceOut)
def create_depot_service(
    data: DepotServiceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    if db.query(DepotService).filter(DepotService.nom == data.nom, DepotService.user_id == parent_user_id).first():
        raise HTTPException(status_code=400, detail="Ce service existe déjà.")

    service = DepotService(**data.dict(), user_id=parent_user_id)
    db.add(service)
    db.commit()
    db.refresh(service)

    log_action(
        db=db,
        current_user=current_user,
        action="Création service de dépôt",
        type_entite="depot_service",
        entite_id=service.id,
        details=f"Service '{service.nom}' créé"
    )
    return service



# 📄 Lister tous les services de dépôt
@router.get("/", response_model=List[DepotServiceOut])
def list_depot_services(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    return db.query(DepotService).filter(DepotService.user_id == parent_user_id).all()
