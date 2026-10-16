from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from math import ceil

from app.database import get_db
from app.models.model_depot import Depot
from app.models.model_client import Client
from app.models.model_depot_tarif import DepotTarif
from app.models.model_depot_service import DepotService
from app.models.model_depot_tarif_items import DepotTarifItem
from app.models.model_facture_depot import FactureDepot
from app.schemas.depot_schema import (
    DepotCancellation,
    DepotCreate,
    DepotOut,
    DepotRestore,
    MessageResponse,
)
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.utils.subscription_guard import (
    enforce_invoice_quota,
    enforce_feature_access,
    resolve_subscription_access,
)
from app.services.depot_pricing_service import calculate_deposit_line
from app.services.depot_workflow_service import (
    InvalidDepositTransition,
    validate_deposit_transition,
)

router = APIRouter(prefix="/depots", tags=["Dépôt - Dépôts"])


def _owner_id(current_user) -> int:
    return (
        current_user.id
        if current_user.is_main_user
        else current_user.parent_user_id
    )


def _locked_depot(db: Session, depot_id: int, owner_id: int) -> Depot:
    depot = (
        db.query(Depot)
        .filter(Depot.id == depot_id, Depot.user_id == owner_id)
        .with_for_update()
        .first()
    )
    if not depot:
        raise HTTPException(
            status_code=404,
            detail="Dépôt introuvable ou non autorisé.",
        )
    return depot


def _ensure_transition(depot: Depot, target: str) -> None:
    try:
        validate_deposit_transition(depot.statut, target)
    except InvalidDepositTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _record_status_change(depot: Depot, current_user, now: datetime) -> None:
    depot.statut_modifie_le = now
    depot.statut_modifie_par = current_user.id

# ➕ Créer un dépôt
@router.post("/", response_model=DepotOut)
def create_depot(
    data: DepotCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = _owner_id(current_user)
    access = resolve_subscription_access(db, current_user)
    existing_depots = db.query(Depot).filter(
        Depot.user_id == parent_user_id
    ).count()
    if existing_depots >= 1 and not access.has_feature("multi_depot"):
        enforce_feature_access(db, current_user, "multi_depot")
    enforce_invoice_quota(db, current_user)

    client = db.query(Client).filter(
        Client.id == data.client_id,
        Client.user_id == parent_user_id,
    ).first()
    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client introuvable dans cette entreprise.",
        )
    service = db.query(DepotService).filter(
        DepotService.id == data.service_id,
        DepotService.user_id == parent_user_id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable ou non autorisé.")

    # Toutes les références sont validées avant la première écriture. Une
    # erreur ne peut donc plus laisser un dépôt orphelin dans la base.
    prepared_items = []
    prix_total = 0.0
    for item in data.tarif_items:
        tarif = db.query(DepotTarif).filter(
            DepotTarif.id == item.tarif_id,
            DepotTarif.user_id == parent_user_id,
            DepotTarif.service_id == data.service_id,
            DepotTarif.actif.is_(True),
        ).first()
        if not tarif:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Tarif ID {item.tarif_id} introuvable, inactif ou "
                    "rattaché à un autre service."
                ),
            )
        calculated = calculate_deposit_line(
            mode=tarif.mode_tarification,
            quantity=item.quantite,
            unit_price=tarif.tarif_unitaire,
            price_per_minute=tarif.tarif_par_minute,
            custom_price=item.prix_personnalise,
        )
        prix_total += calculated.total
        prepared_items.append((item, calculated))

    try:
        depot = Depot(
            client_id=data.client_id,
            service_id=data.service_id,
            description_bien=data.description_bien.strip(),
            statut="en_attente",
            prix_total=round(prix_total, 2),
            user_id=parent_user_id,
        )
        db.add(depot)
        db.flush()

        for item, calculated in prepared_items:
            db.add(
                DepotTarifItem(
                    depot_id=depot.id,
                    tarif_id=item.tarif_id,
                    quantite=item.quantite,
                    prix_personnalise=item.prix_personnalise,
                    description=(item.description or "").strip() or None,
                    mode_tarification_snapshot=calculated.mode,
                    prix_unitaire_snapshot=calculated.unit_price,
                    montant_total=calculated.total,
                )
            )

        facture_depot = FactureDepot(
            depot_id=depot.id,
            client_id=depot.client_id,
            montant_ht=round(prix_total, 2),
            tva=0,
            montant_ttc=round(prix_total, 2),
            statut="en_attente",
            date_facture=datetime.utcnow(),
            user_id=parent_user_id,
        )
        db.add(facture_depot)
        db.flush()

        log_action(
            db=db,
            current_user=current_user,
            action="Création dépôt + facture",
            type_entite="depot",
            entite_id=depot.id,
            details=(
                f"Dépôt créé avec FactureDepot pour client "
                f"{depot.client_id} : {depot.description_bien}"
            ),
            commit=False,
        )
        db.commit()
        db.refresh(depot)
    except Exception:
        db.rollback()
        raise

    return depot

# 📄 Lister tous les dépôts  # importe ton modèle si ce n’est pas déjà fait

@router.get("/", response_model=List[DepotOut])
def list_depots(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = _owner_id(current_user)
    depots = db.query(Depot).filter(Depot.user_id == parent_user_id).order_by(Depot.date_depot.desc()).all()

    # reste du code identique...


    result = []
    for depot in depots:
        # 🔎 On cherche la facture de dépôt associée
        facture_depot = (
            db.query(FactureDepot)
            .filter(FactureDepot.depot_id == depot.id)
            .filter(FactureDepot.user_id == parent_user_id)
            .first()
        )

        # 🆕 Charger tous les tarifs multiples associés à ce dépôt
        tarif_items = []
        for item in depot.tarif_items:  # relation SQLAlchemy
            tarif_items.append({
                "tarif_id": item.tarif_id,
                "quantite": item.quantite,
                "prix_personnalise": item.prix_personnalise,
                "description": item.description,
                "mode_tarification_snapshot": getattr(
                    item, "mode_tarification_snapshot", None
                ),
                "prix_unitaire_snapshot": getattr(
                    item, "prix_unitaire_snapshot", None
                ),
                "montant_total": getattr(item, "montant_total", None),
            })

        result.append({
            "id": depot.id,
            "client_id": depot.client_id,
            "client_nom": depot.client.nom if depot.client else "",
            "service_id": depot.service_id,
            "tarif_id": depot.tarif_id,
            "description_bien": depot.description_bien,
            "date_depot": depot.date_depot,
            "date_stockage": depot.date_stockage,
            "date_pret_retrait": depot.date_pret_retrait,
            "date_retrait": depot.date_retrait,
            "date_annulation": depot.date_annulation,
            "motif_annulation": depot.motif_annulation,
            "statut_modifie_le": depot.statut_modifie_le,
            "statut_modifie_par": depot.statut_modifie_par,
            "statut": depot.statut,
            "prix_personnalise": depot.prix_personnalise,
            "duree_minutes": depot.duree_minutes,
            "prix_total": depot.prix_total,
            
            "facture_depot_id": facture_depot.id if facture_depot else None,
            "tarif_items": tarif_items,  # ✅ inclus dans DepotOut
        })
    return result


@router.put("/{depot_id}/stocker", response_model=MessageResponse)
def stocker_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])
    ),
):
    depot = _locked_depot(db, depot_id, _owner_id(current_user))
    _ensure_transition(depot, "stocke")
    now = datetime.utcnow()
    depot.statut = "stocke"
    depot.date_stockage = now
    _record_status_change(depot, current_user, now)
    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Mise en stockage d'un dépôt",
            type_entite="depot",
            entite_id=depot.id,
            details=f"Dépôt placé en stockage : {depot.description_bien}",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Dépôt marqué comme stocké."}


@router.put("/{depot_id}/pret-retrait", response_model=MessageResponse)
def marquer_depot_pret_retrait(
    depot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])
    ),
):
    depot = _locked_depot(db, depot_id, _owner_id(current_user))
    _ensure_transition(depot, "pret_retrait")
    now = datetime.utcnow()
    depot.statut = "pret_retrait"
    depot.date_pret_retrait = now
    _record_status_change(depot, current_user, now)
    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Dépôt prêt au retrait",
            type_entite="depot",
            entite_id=depot.id,
            details=f"Dépôt prêt au retrait : {depot.description_bien}",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Dépôt marqué comme prêt au retrait."}


@router.put("/{depot_id}/annuler", response_model=MessageResponse)
def annuler_depot(
    depot_id: int,
    payload: DepotCancellation,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])
    ),
):
    owner_id = _owner_id(current_user)
    depot = _locked_depot(db, depot_id, owner_id)
    _ensure_transition(depot, "annule")
    now = datetime.utcnow()
    depot.statut = "annule"
    depot.date_annulation = now
    depot.motif_annulation = payload.motif.strip()
    _record_status_change(depot, current_user, now)
    facture = db.query(FactureDepot).filter(
        FactureDepot.depot_id == depot.id,
        FactureDepot.user_id == owner_id,
    ).first()
    if facture and facture.statut not in {"paye", "payee", "soldee"}:
        facture.statut = "annulee"
    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Annulation dépôt",
            type_entite="depot",
            entite_id=depot.id,
            details=f"Motif : {depot.motif_annulation}",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Dépôt annulé avec traçabilité."}


@router.put("/{depot_id}/restaurer", response_model=MessageResponse)
def restaurer_depot(
    depot_id: int,
    payload: DepotRestore,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin])),
):
    owner_id = _owner_id(current_user)
    depot = _locked_depot(db, depot_id, owner_id)
    _ensure_transition(depot, "recu")
    now = datetime.utcnow()
    # ``en_attente`` reste la représentation persistée temporaire de ``recu``
    # afin que les versions mobiles déjà installées restent compatibles.
    depot.statut = "en_attente"
    depot.date_annulation = None
    depot.motif_annulation = None
    _record_status_change(depot, current_user, now)
    facture = db.query(FactureDepot).filter(
        FactureDepot.depot_id == depot.id,
        FactureDepot.user_id == owner_id,
    ).first()
    if facture and facture.statut == "annulee":
        facture.statut = "en_attente"
    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Restauration dépôt annulé",
            type_entite="depot",
            entite_id=depot.id,
            details=(payload.motif or "Restauration administrative").strip(),
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Dépôt restauré dans l'état reçu."}



# ✅ Marquer un dépôt comme "retiré"
@router.put("/{depot_id}/retirer", response_model=MessageResponse)
def retirer_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = _owner_id(current_user)
    depot = _locked_depot(db, depot_id, parent_user_id)
    _ensure_transition(depot, "retire")

    depot.date_retrait = datetime.utcnow()
    depot.statut = "retire"
    _record_status_change(depot, current_user, depot.date_retrait)

    duree_minutes = max(
        0,
        ceil((depot.date_retrait - depot.date_depot).total_seconds() / 60),
    )
    depot.duree_minutes = duree_minutes
    prix_total = 0.0
    for item in depot.tarif_items:
        tarif = item.tarif
        mode = getattr(item, "mode_tarification_snapshot", None) or (
            tarif.mode_tarification if tarif else "unitaire"
        )
        snapshot_price = getattr(item, "prix_unitaire_snapshot", None)
        if snapshot_price is None:
            snapshot_price = (
                tarif.tarif_par_minute
                if mode in ("duree", "durée", "minute", "minutes")
                else tarif.tarif_unitaire
            ) if tarif else 0
        calculated = calculate_deposit_line(
            mode=mode,
            quantity=item.quantite,
            unit_price=snapshot_price,
            price_per_minute=snapshot_price,
            custom_price=item.prix_personnalise,
            duration_minutes=duree_minutes,
        )
        item.mode_tarification_snapshot = calculated.mode
        item.prix_unitaire_snapshot = calculated.unit_price
        item.montant_total = calculated.total
        prix_total += calculated.total

    depot.prix_total = round(prix_total, 2)
    facture = db.query(FactureDepot).filter(
        FactureDepot.depot_id == depot.id,
        FactureDepot.user_id == parent_user_id,
    ).first()
    if not facture:
        raise HTTPException(
            status_code=409,
            detail="La facture associée au dépôt est introuvable.",
        )
    facture.montant_ht = depot.prix_total
    facture.montant_ttc = round(depot.prix_total + float(facture.tva or 0), 2)

    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Retrait dépôt",
            type_entite="depot",
            entite_id=depot.id,
            details=(
                f"Dépôt retiré pour client {depot.client_id} : "
                f"{depot.description_bien}; durée={duree_minutes} min; "
                f"total={depot.prix_total}"
            ),
            commit=False,
        )
        db.commit()
        db.refresh(depot)
    except Exception:
        db.rollback()
        raise

    return {"message": "Dépôt retiré et facture recalculée avec succès"}

