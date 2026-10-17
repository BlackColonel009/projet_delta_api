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
from sqlalchemy import func
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter

router = APIRouter(prefix="/depot-services", tags=["Dépôt - Services"])

# ➕ Créer un service de dépôt
@router.post("/", response_model=DepotServiceOut)
def create_depot_service(
    data: DepotServiceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    normalized_name = data.nom.strip()
    if db.query(DepotService).filter(
        func.lower(DepotService.nom) == normalized_name.lower(),
        enterprise_scope_filter(DepotService, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Ce service existe déjà.")

    service = DepotService(
        **data.model_dump(exclude={"nom"}),
        nom=normalized_name,
        user_id=parent_user_id,
        enterprise_id=enterprise_id,
    )
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
    return db.query(DepotService).filter(
        enterprise_scope_filter(DepotService, current_user)
    ).all()
