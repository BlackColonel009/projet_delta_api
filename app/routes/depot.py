from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.model_depot import Depot
from app.models.model_depot_tarif import DepotTarif
from app.models.model_depot_service import DepotService
from app.models.model_depot_tarif_items import DepotTarifItem
from app.models.model_facture_depot import FactureDepot
from app.schemas.depot_schema import DepotCreate, DepotOut, MessageResponse
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action

router = APIRouter(prefix="/depots", tags=["Dépôt - Dépôts"])

# ➕ Créer un dépôt
@router.post("/", response_model=DepotOut)
def create_depot(
    data: DepotCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    service = db.query(DepotService).filter(
        DepotService.id == data.service_id,
        DepotService.user_id == parent_user_id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable ou non autorisé.")

    depot = Depot(
        client_id=data.client_id,
        service_id=data.service_id,
        description_bien=data.description_bien,
        statut="en_attente",
        prix_total=0,
        user_id=current_user.id  # <-- liaison user_id ici
    )
    db.add(depot)
    db.commit()
    db.refresh(depot)

    # Suite du code identique...


    prix_total = 0.0

    # 3. Enregistrer chaque tarif sélectionné
    for item in data.tarif_items:
        tarif = db.query(DepotTarif).filter(DepotTarif.id == item.tarif_id).first()
        if not tarif:
            raise HTTPException(status_code=404, detail=f"Tarif ID {item.tarif_id} introuvable.")

        if item.prix_personnalise is not None:
            prix = item.prix_personnalise * item.quantite
        elif tarif.mode_tarification == "unitaire":
            prix = (tarif.tarif_unitaire or 0) * item.quantite
        elif tarif.mode_tarification == "minute":
            prix = (tarif.tarif_par_minute or 0) * item.quantite
        else:
            prix = 0

        prix_total += prix

        # ✅ Lier le tarif au dépôt
        tarif_item = DepotTarifItem(
            depot_id=depot.id,
            tarif_id=item.tarif_id,
            quantite=item.quantite,
            prix_personnalise=item.prix_personnalise,
            description=item.description if item.description else None
        )
        db.add(tarif_item)

    # 4. Mettre à jour le prix total du dépôt
    depot.prix_total = prix_total
    db.commit()

    # 5. Créer automatiquement la facture de dépôt
    montant_ht = prix_total
    tva = 0  # à adapter si besoin
    montant_ttc = montant_ht + tva

    facture_depot = FactureDepot(
        depot_id=depot.id,
        client_id=depot.client_id,
        montant_ht=montant_ht,
        tva=tva,
        montant_ttc=montant_ttc,
        statut="en_attente",
        date_facture=datetime.utcnow(),
        user_id=current_user.id
    )
    db.add(facture_depot)
    db.commit()
    db.refresh(facture_depot)

    depot.facture_depot_id = facture_depot.id
    db.commit()

    # 6. Audit log
    log_action(
        db=db,
        current_user=current_user,
        action="Création dépôt + facture",
        type_entite="depot",
        entite_id=depot.id,
        details=f"Dépôt créé avec FactureDepot pour client {depot.client_id} : {depot.description_bien}"
    )

    return depot

# 📄 Lister tous les dépôts  # importe ton modèle si ce n’est pas déjà fait

@router.get("/", response_model=List[DepotOut])
def list_depots(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    depots = db.query(Depot).filter(Depot.user_id == parent_user_id).order_by(Depot.date_depot.desc()).all()

    # reste du code identique...


    result = []
    for depot in depots:
        # 🔎 On cherche la facture de dépôt associée
        facture_depot = (
            db.query(FactureDepot)
            .filter(FactureDepot.depot_id == depot.id)
            .first()
        )

        # 🆕 Charger tous les tarifs multiples associés à ce dépôt
        tarif_items = []
        for item in depot.tarif_items:  # relation SQLAlchemy
            tarif_items.append({
                "tarif_id": item.tarif_id,
                "quantite": item.quantite,
                "prix_personnalise": item.prix_personnalise,
            })

        result.append({
            "id": depot.id,
            "client_id": depot.client_id,
            "client_nom": depot.client.nom if depot.client else "",
            "service_id": depot.service_id,
            "tarif_id": depot.tarif_id,
            "description_bien": depot.description_bien,
            "date_depot": depot.date_depot,
            "date_retrait": depot.date_retrait,
            "statut": depot.statut,
            "prix_personnalise": depot.prix_personnalise,
            "duree_minutes": depot.duree_minutes,
            "prix_total": depot.prix_total,
            
            "facture_depot_id": facture_depot.id if facture_depot else None,
            "tarif_items": tarif_items,  # ✅ inclus dans DepotOut
        })
    return result



# ✅ Marquer un dépôt comme "retiré"
@router.put("/{depot_id}/retirer", response_model=MessageResponse)
def retirer_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    depot = db.query(Depot).filter(
        Depot.id == depot_id,
        Depot.user_id == parent_user_id
    ).first()
    if not depot:
        raise HTTPException(status_code=404, detail="Dépôt introuvable ou non autorisé.")
    if depot.date_retrait:
        raise HTTPException(status_code=400, detail="Ce dépôt a déjà été retiré.")

    depot.date_retrait = datetime.utcnow()
    depot.statut = "retire"

    # Calcul du prix si mode durée
    if depot.tarif_id:
        tarif = db.query(DepotTarif).filter(DepotTarif.id == depot.tarif_id).first()
        if tarif and tarif.mode_tarification == "duree":
            duree_minutes = int((depot.date_retrait - depot.date_depot).total_seconds() // 60)
            depot.duree_minutes = duree_minutes
            depot.prix_total = (tarif.tarif_par_minute or 0) * duree_minutes

    db.commit()
    db.refresh(depot)

    log_action(
        db=db,
        current_user=current_user,
        action="Retrait dépôt",
        type_entite="depot",
        entite_id=depot.id,
        details=f"Dépôt retiré pour client {depot.client_id} : {depot.description_bien}"
    )

    return {"message": "Dépôt marqué comme retiré"}

