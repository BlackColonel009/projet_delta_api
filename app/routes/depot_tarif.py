from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.model_depot_tarif import DepotTarif
from app.models.model_depot_service import DepotService
from app.schemas.depot_tarif_schema import DepotTarifCreate, DepotTarifOut
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/depot-tarifs", tags=["Dépôt - Tarifs"])

# ➕ Créer un tarif pour un service
@router.post("/", response_model=DepotTarifOut)
def create_tarif(
    data: DepotTarifCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    service = db.query(DepotService).filter(
        DepotService.id == data.service_id,
        DepotService.user_id == parent_user_id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable ou non autorisé.")

    tarif = DepotTarif(**data.dict(exclude={"service_nom"}), user_id=parent_user_id)
    db.add(tarif)
    db.commit()
    db.refresh(tarif)

    # Recharger avec relation service pour que service_nom fonctionne
    tarif = db.query(DepotTarif).options(joinedload(DepotTarif.service)).get(tarif.id)

    log_action(
        db=db,
        current_user=current_user,
        action="Création tarif dépôt",
        type_entite="depot_tarif",
        entite_id=tarif.id,
        details=f"Tarif '{tarif.nom_tarif}' créé pour service '{service.nom}'"
    )
    return tarif

# 📄 Lister les tarifs d'un service
@router.get("/", response_model=List[DepotTarifOut])
def list_tarifs(
    service_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(DepotTarif).join(DepotService).filter(DepotService.user_id == parent_user_id)

    if service_id:
        query = query.filter(DepotTarif.service_id == service_id)

    tarifs = query.order_by(DepotTarif.nom_tarif.asc()).all()

    result = [
        DepotTarifOut(
            id=tarif.id,
            nom_tarif=tarif.nom_tarif,
            mode_tarification=tarif.mode_tarification,
            tarif_unitaire=tarif.tarif_unitaire,
            tarif_par_minute=tarif.tarif_par_minute,
            service_id=tarif.service_id,
            service_nom=tarif.service.nom if tarif.service else "Inconnu",
            actif=tarif.actif,
            date_creation=tarif.date_creation
        )
        for tarif in tarifs
    ]
    return result


# 📄 Update des tarifs
@router.put("/{tarif_id}", response_model=DepotTarifOut)
def update_tarif(
    tarif_id: int,
    data: DepotTarifCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    tarif = db.query(DepotTarif).join(DepotService).filter(
        DepotTarif.id == tarif_id,
        DepotService.user_id == parent_user_id
    ).first()
    if not tarif:
        raise HTTPException(status_code=404, detail="Tarif introuvable ou non autorisé.")

    for key, value in data.dict().items():
        setattr(tarif, key, value)

    db.commit()
    db.refresh(tarif)

    log_action(
        db=db,
        current_user=current_user,
        action="Modification tarif dépôt",
        type_entite="depot_tarif",
        entite_id=tarif.id,
        details=f"Tarif modifié : {tarif.nom_tarif}"
    )
    return tarif

