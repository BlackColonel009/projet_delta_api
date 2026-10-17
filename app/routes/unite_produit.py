# app/routes/unite_produit.py

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_unite_produit import UniteProduit
from app.models.model_produit import Produit
from app.schemas.unite_produit_schema import (
    AddUnitesRequest,
    StockCleanupRequest,
    UniteProduitOut,
)
from app.utils.security import get_current_user, require_main_user, require_super_user
from app.utils.permissions import All_required, check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.services.traceability_service import create_generated_unit
from app.utils.subscription_guard import require_subscription_feature
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)
from app.utils.enterprise_context import (
    ActiveEnterpriseContext,
    get_active_enterprise_context,
)
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import List, Optional

router = APIRouter(prefix="/unites-produit", tags=["Unités Produit"])

STOCK_CLEANUP_CONFIRMATION = "VIDER LE STOCK"
STOCK_CLEANUP_STATUSES = ("disponible", "indisponible")


def _normalized_status(status: Optional[str]) -> str:
    return (status or "").strip().lower()

@router.post(
    "/add/{produit_id}",
    dependencies=[Depends(require_subscription_feature("full_qr"))],
)
def add_unites_to_produit(
    produit_id: int,
    data: AddUnitesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    # 🔍 Récupérer le produit
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
        Produit.date_suppression.is_(None),
    ).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    # # 🚫 Vérification : si le produit contient déjà des codes-barres scannés
    # if produit.a_des_barcodes:
    #     raise HTTPException(
    #         status_code=400,
    #         detail="❌ Ce produit contient déjà des unités avec code-barres. L’ajout d’unités avec QR est désactivé pour éviter les conflits."
    #     )

    created = []
    
    if data.tracabilites:
        # 🧠 Mode manuel : utiliser les tracabilités données
        if len(data.tracabilites) != data.nombre:
            raise HTTPException(status_code=400, detail="Le nombre de tracabilités fournies ne correspond pas à 'nombre'.")

        normalized_traces = list(dict.fromkeys(
            value.strip()
            for value in data.tracabilites
            if value and value.strip()
        ))
        if len(normalized_traces) != data.nombre:
            raise HTTPException(
                status_code=400,
                detail="Les traçabilités doivent être uniques et non vides.",
            )
        existing = {
            value
            for (value,) in db.query(UniteProduit.tracabilite).filter(
                UniteProduit.tracabilite.in_(normalized_traces)
            ).all()
        }
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ces traçabilités existent déjà : "
                    + ", ".join(sorted(existing)[:5])
                ),
            )

        for tracabilite in normalized_traces:
            unite = UniteProduit(
                produit_id=produit.id,
                enterprise_id=enterprise_id,
                tracabilite=tracabilite,
                statut="disponible",
                date_creation=datetime.utcnow()
            )
            db.add(unite)
            created.append(tracabilite)

    else:
        # ⚙️ Mode automatique
        for _ in range(data.nombre):
            unite = create_generated_unit(
                db,
                produit_id=produit.id,
                suffix=data.prefixe.removesuffix("-") if data.prefixe != "TRAC-" else None,
            )
            created.append(unite.tracabilite)

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Ajout unités",
        type_entite="produit",
        entite_id=produit.id,
        details=f"{data.nombre} unités ajoutées {'manuellement' if data.tracabilites else 'automatiquement'} pour produit {produit.nom}"
    )

    return {"message": "Unités ajoutées avec succès", "tracabilites": created}


#reccuperer par id
@router.get("/produits/{produit_id}/unites")
def list_unites_for_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    from app.models.model_unite_produit import UniteProduit

    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.produit_id == produit_id,  # ✅ filtre ajouté
        enterprise_scope_filter(Produit, current_user),
    ).order_by(UniteProduit.date_creation.desc()).all()

    return [
        {
            "id": u.id,
            "tracabilite": u.tracabilite,
            "code_barre": u.code_barre,
            "statut": u.statut,
            "date_creation": u.date_creation.isoformat() if u.date_creation else None,
            "date_modification": u.date_modification.isoformat() if u.date_modification else None,
        }
        for u in unites
    ]


#reccuperer unité disponible
@router.get("/disponibles")  # ou /toutes si tu veux encore plus large
def list_unites_visibles(
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)

    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut.in_(["disponible", "indisponible", "vendu", "en cours"]),  # ✅ inclut les deux
        enterprise_scope_filter(Produit, current_user),
    ).all()

    return [
        {
            "id": u.id,
            "produit_id": u.produit_id,
            "nom_produit": u.produit.nom,
            "statut": u.statut,
            "tracabilite": u.tracabilite,
            "date_creation": u.date_creation.strftime('%Y-%m-%d %H:%M'),
            "date_modification": u.date_modification.strftime('%Y-%m-%d %H:%M') if u.date_modification else None
        }
        for u in unites
    ]

    
    

# ✅ 2. Route de purge des unités "temp"
@router.delete("/purge-temp")
def purge_temp_units(
    db: Session = Depends(get_db),
    current_user=Depends(require_super_user),
):
    deleted = db.query(UniteProduit).filter(
        UniteProduit.statut == "temp",
        UniteProduit.produit_id.is_(None),
    ).delete(synchronize_session=False)
    db.commit()

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Purge",
    #     type_entite="unite_produit",
    #     entite_id=None,
    #     details=f"{deleted} unités temporaires supprimées"
    # )

    return {
        "message": f"{deleted} unités 'temp' supprimées.",
        "deleted_count": deleted
    }


@router.get("/stock-cleanup-preview")
def preview_stock_cleanup(
    db: Session = Depends(get_db),
    current_user=Depends(require_main_user),
    enterprise_context: ActiveEnterpriseContext = Depends(
        get_active_enterprise_context
    ),
):
    """Retourne uniquement les volumes; cette route ne modifie aucune donnée."""
    status_rows = (
        db.query(UniteProduit.statut, func.count(UniteProduit.id))
        .join(UniteProduit.produit)
        .filter(Produit.enterprise_id == enterprise_context.enterprise_id)
        .group_by(UniteProduit.statut)
        .all()
    )
    counts = {
        _normalized_status(status): int(count)
        for status, count in status_rows
    }
    available_count = counts.get("disponible", 0)
    unavailable_count = counts.get("indisponible", 0)
    sold_count = counts.get("vendu", 0)
    in_progress_count = counts.get("en cours", 0)
    affected_products = (
        db.query(func.count(func.distinct(UniteProduit.produit_id)))
        .join(UniteProduit.produit)
        .filter(
            Produit.enterprise_id == enterprise_context.enterprise_id,
            UniteProduit.statut.in_(STOCK_CLEANUP_STATUSES),
        )
        .scalar()
        or 0
    )

    return {
        "eligible_count": available_count + unavailable_count,
        "available_count": available_count,
        "unavailable_count": unavailable_count,
        "protected_count": sold_count + in_progress_count,
        "sold_count": sold_count,
        "in_progress_count": in_progress_count,
        "affected_products": int(affected_products),
    }


@router.delete("/stock-cleanup")
def cleanup_company_stock(
    data: StockCleanupRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_main_user),
    enterprise_context: ActiveEnterpriseContext = Depends(
        get_active_enterprise_context
    ),
):
    """Supprime définitivement les unités disponibles/indisponibles de l'entreprise."""
    if data.confirmation.strip().upper() != STOCK_CLEANUP_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f'Tapez exactement « {STOCK_CLEANUP_CONFIRMATION} » pour confirmer.',
        )

    eligible_units = (
        db.query(UniteProduit)
        .join(UniteProduit.produit)
        .filter(
            Produit.enterprise_id == enterprise_context.enterprise_id,
            UniteProduit.statut.in_(STOCK_CLEANUP_STATUSES),
        )
        .all()
    )
    # Défense supplémentaire : une unité ayant changé d'état ne doit jamais être supprimée.
    eligible_units = [
        unit
        for unit in eligible_units
        if _normalized_status(unit.statut) in STOCK_CLEANUP_STATUSES
    ]
    unit_ids = [unit.id for unit in eligible_units]
    product_ids = {unit.produit_id for unit in eligible_units if unit.produit_id}
    available_count = sum(
        _normalized_status(unit.statut) == "disponible" for unit in eligible_units
    )
    unavailable_count = sum(
        _normalized_status(unit.statut) == "indisponible" for unit in eligible_units
    )

    try:
        deleted_count = 0
        if unit_ids:
            deleted_count = (
                db.query(UniteProduit)
                .filter(
                    UniteProduit.id.in_(unit_ids),
                    UniteProduit.statut.in_(STOCK_CLEANUP_STATUSES),
                )
                .delete(synchronize_session=False)
            )

        if product_ids:
            products = (
                db.query(Produit)
                .filter(
                    Produit.id.in_(product_ids),
                    Produit.enterprise_id == enterprise_context.enterprise_id,
                )
                .all()
            )
            for product in products:
                product.quantite = (
                    db.query(UniteProduit)
                    .filter(
                        UniteProduit.produit_id == product.id,
                        UniteProduit.statut == "disponible",
                    )
                    .count()
                )
                product.date_modification = datetime.utcnow()

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Le stock n'a pas pu être vidé. Aucune suppression partielle n'a été conservée.",
        )

    log_action(
        db=db,
        current_user=current_user,
        action="Nettoyage définitif du stock",
        type_entite="unite_produit",
        entite_id=None,
        details=(
            f"{deleted_count} unités supprimées définitivement "
            f"({available_count} disponibles, {unavailable_count} indisponibles). "
            "Les unités vendues et en cours ont été conservées."
        ),
    )
    return {
        "message": "Le stock disponible et indisponible a été vidé.",
        "deleted_count": int(deleted_count),
        "available_count": available_count,
        "unavailable_count": unavailable_count,
    }

#suppression d'unité-produit
@router.delete("/{unite_id}")
def delete_unite_produit(
    unite_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    unite = (
        db.query(UniteProduit)
        .join(UniteProduit.produit)
        .filter(
            UniteProduit.id == unite_id,
            enterprise_scope_filter(Produit, current_user),
        )
        .first()
    )
    if not unite:
        raise HTTPException(status_code=404, detail="Unité non trouvée")

    if _normalized_status(unite.statut) != "disponible":
        raise HTTPException(
            status_code=409,
            detail=(
                "Seule une unité disponible peut être retirée du stock. "
                "Les unités vendues ou en cours sont protégées."
            ),
        )

    produit = unite.produit  # récupération avant suppression

    # Supprimer l'unité
    unite.statut = "indisponible"
    unite.date_modification = datetime.utcnow()
    db.commit()

    # 🔁 Recalculer la quantité restante
    quantite_restante = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit.id,
        UniteProduit.statut == "disponible"
    ).count()

    # Mettre à jour le champ produit.quantite
    produit.quantite = quantite_restante
    db.commit()

    # Logger
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression unité",
        type_entite="unite_produit",
        entite_id=unite.id,
        details=f"Unité QR supprimée : {unite.tracabilite} (produit {produit.nom}) quantité restante: {produit.quantite}"
    )

    return {
        "message": f"Unité supprimée : {unite.tracabilite}",
        "quantite_restante": quantite_restante,
        "produit_id": produit.id,
        "produit_nom": produit.nom
    }

# **************************CODE BARRE STEP**************************************

# 🧪 Enregistrer une série de codes-barres en statut temporaire (avant liaison produit)
@router.post(
    "/temp",
    dependencies=[Depends(require_subscription_feature("full_qr"))],
)
def store_temp_barcodes(
    barcodes: List[str],
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    enterprise_id = actor_enterprise_id(current_user)
    inserted = 0
    for code in barcodes:
        # Vérifie si le code existe déjà
        exist = db.query(UniteProduit).filter(
            UniteProduit.code_barre == code,
            UniteProduit.enterprise_id == enterprise_id,
        ).first()
        if exist:
            continue  # ne pas dupliquer

        unite = UniteProduit(
            tracabilite=code,
            code_barre=code,
            statut="temp",
            produit_id=None,
            enterprise_id=enterprise_id,
            date_creation=datetime.utcnow()
        )
        db.add(unite)
        inserted += 1

    db.commit()
    return {"message": f"{inserted} unités temporaires enregistrées."}

# 🔗 Lier une série de codes-barres (déjà scannés) à un produit
# 🔁 Mise à jour : lier des codes-barres à un produit
@router.post(
    "/lier/{produit_id}",
    dependencies=[Depends(require_subscription_feature("full_qr"))],
)
def lier_barcodes_a_produit(
    produit_id: int,
    barcodes: List[str],
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
        Produit.date_suppression.is_(None),
    ).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    now = datetime.utcnow()
    added = []
    already_linked = []
    conflicts = []

    normalized_codes = list(dict.fromkeys(
        code.strip() for code in barcodes if code and code.strip()
    ))
    if not normalized_codes:
        raise HTTPException(status_code=400, detail="Aucun code-barres valide")

    for code in normalized_codes:
        unite = db.query(UniteProduit).filter(
            UniteProduit.code_barre == code,
            UniteProduit.enterprise_id == enterprise_id,
        ).first()
        if unite:
            if unite.produit_id == produit_id:
                already_linked.append(code)
                continue
            if unite.produit_id is not None:
                conflicts.append(code)
                continue
            unite.produit_id = produit_id
            unite.statut = "disponible"
            unite.date_creation = now
            unite.date_modification = now
        else:
            unite = UniteProduit(
                produit_id=produit_id,
                enterprise_id=enterprise_id,
                tracabilite=code,
                code_barre=code,
                statut="disponible",
                date_creation=now,
            )
            db.add(unite)
        added.append(code)

    if conflicts:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Certains codes-barres appartiennent déjà à une autre fiche : "
                + ", ".join(conflicts[:5])
            ),
        )

    db.flush()
    produit.a_des_barcodes = True
    produit.quantite = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.statut == "disponible",
    ).count()
    produit.date_modification = now
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Ajout de codes-barres",
        type_entite="produit",
        entite_id=produit.id,
        details=f"{len(added)} nouvelles unités ajoutées au produit {produit.nom}",
    )

    return {
        "message": f"{len(added)} nouvelles unités ajoutées au produit {produit.nom}",
        "added_count": len(added),
        "added_codes": added,
        "already_linked": already_linked,
        "quantity": produit.quantite,
        "added_at": now.isoformat(),
    }


@router.post("/infos")
def get_produits_par_codes(
    barcodes: List[str],
    db: Session = Depends(get_db),
    current_user = Depends(All_required()),
):
    parent_user_id = actor_owner_id(current_user)
    regroupement = {}
    invalid_codes = []

    for code in barcodes:
        unite = db.query(UniteProduit).filter(
            UniteProduit.tracabilite == code,
            UniteProduit.produit_id.isnot(None),
            UniteProduit.statut == "disponible"
        ).join(UniteProduit.produit).filter(
            enterprise_scope_filter(Produit, current_user),
        ).first()

        if not unite or not unite.produit:
            invalid_codes.append(code)
            continue

        pid = unite.produit.id
        if pid not in regroupement:
            regroupement[pid] = {
                "produit": unite.produit,
                "codes": []
            }
        regroupement[pid]["codes"].append(code)

    return {
        "produits": list(regroupement.values()),
        "invalid_codes": invalid_codes
    }


# ✅ 3. Rechercher une unité via code_barre
@router.get("/by-barcode/{code}", response_model=UniteProduitOut)
def get_unite_by_barcode(
    code: str,
    db: Session = Depends(get_db),
    current_user = Depends(All_required()),
):
    parent_user_id = actor_owner_id(current_user)
    unite = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.code_barre == code,
        enterprise_scope_filter(Produit, current_user),
    ).first()
    if not unite:
        raise HTTPException(status_code=404, detail="Code-barre introuvable")
    return unite

# #modification d'unité statut
# @router.put("/set-statut/{unite_id}")
# def set_statut_unite(
#     unite_id: int,
#     statut: str = Body(...),
#     db: Session = Depends(get_db),
#     current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
# ):
#     unite = db.query(UniteProduit).filter(UniteProduit.id == unite_id).first()
#     if not unite:
#         raise HTTPException(status_code=404, detail="Unité non trouvée")

#     unite.statut = statut
#     unite.date_modification = datetime.utcnow()
#     db.commit()

#     return {
#         "message": f"Statut de l'unité {unite.tracabilite} mis à jour : {statut}"
#     }
