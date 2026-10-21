from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models.model_categorie import Categorie
from app.models.model_enterprise import Enterprise
from app.models.model_fournisseur import Fournisseur
from app.models.model_historique_general import Historique
from app.models.model_produit import Produit
from app.models.model_stock_arrival import (
    StockArrival,
    StockArrivalLine,
    StockArrivalUnit,
    StockTransfer,
    StockTransferLine,
    StockTransferUnit,
)
from app.models.model_unite_produit import UniteProduit
from app.schemas.stock_arrival_schema import (
    ArrivalTransferCreate,
    StockArrivalCreate,
    StockArrivalLineCreate,
    StockTransferCreate,
    StockTransferItem,
)
from app.schemas.user_schema import RoleEnum
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id
from app.services.traceability_service import create_generated_unit
from app.utils.logger import log_action
from app.utils.permissions import check_role


router = APIRouter(prefix="/stock-arrivals", tags=["Nouveaux arrivages"])


def _agent_name(actor) -> str:
    return str(
        getattr(actor, "username", None)
        or getattr(actor, "email", None)
        or "Agent Trade Care"
    )


def _require_commerce(db: Session, enterprise_id: int) -> Enterprise:
    enterprise = db.query(Enterprise).filter(
        Enterprise.id == enterprise_id,
        Enterprise.status == "active",
    ).first()
    if not enterprise:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    if enterprise.business_type != "commerce":
        raise HTTPException(
            status_code=409,
            detail="Les arrivages sont disponibles uniquement dans les entreprises Commerce.",
        )
    return enterprise


def _arrival_or_404(db: Session, actor, arrival_id: int, lock: bool = False):
    query = db.query(StockArrival).filter(
        StockArrival.id == arrival_id,
        StockArrival.enterprise_id == actor_enterprise_id(actor),
    )
    if lock:
        query = query.with_for_update()
    arrival = query.first()
    if not arrival:
        raise HTTPException(status_code=404, detail="Arrivage introuvable")
    return arrival


def _assert_draft(arrival: StockArrival):
    if arrival.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Seul un arrivage en brouillon peut être modifié.",
        )


def _serialize_unit(link: StockArrivalUnit) -> dict:
    unit = link.unit
    current_enterprise = unit.enterprise
    return {
        "id": unit.id,
        "traceability": link.traceability_snapshot,
        "barcode": link.barcode_snapshot,
        "status": unit.statut,
        "created_at": unit.date_creation,
        "current_enterprise_id": unit.enterprise_id,
        "current_enterprise_name": current_enterprise.name if current_enterprise else None,
        "current_product_id": unit.produit_id,
        "current_product_name": unit.produit.nom if unit.produit else None,
        "transferred": unit.enterprise_id != link.line.enterprise_id,
    }


def _serialize_line(line: StockArrivalLine, include_units: bool = False) -> dict:
    product = line.product
    result = {
        "id": line.id,
        "product_id": line.product_id,
        "product_name": product.nom,
        "product_image": product.image_url,
        "category_name": product.categorie.nom if product.categorie else None,
        "quantity": line.quantity,
        "barcodes": list(line.barcodes_json or []),
        "qr_count": len(line.units),
        "notes": line.notes,
        "created_at": line.created_at,
    }
    if include_units:
        result["units"] = [_serialize_unit(link) for link in line.units]
    return result


def _serialize_arrival(arrival: StockArrival, detailed: bool = False) -> dict:
    lines = arrival.lines or []
    return {
        "id": arrival.id,
        "name": arrival.name,
        "reference": arrival.reference,
        "notes": arrival.notes,
        "status": arrival.status,
        "supplier": (
            {"id": arrival.supplier.id, "name": arrival.supplier.nom}
            if arrival.supplier
            else None
        ),
        "created_by_name": arrival.created_by_name,
        "created_at": arrival.created_at,
        "updated_at": arrival.updated_at,
        "validated_at": arrival.validated_at,
        "product_count": len(lines),
        "total_quantity": sum(line.quantity for line in lines),
        "lines": [
            _serialize_line(line, include_units=detailed) for line in lines
        ] if detailed else None,
    }


@router.get("")
def list_arrivals(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    enterprise_id = actor_enterprise_id(current_user)
    _require_commerce(db, enterprise_id)
    query = db.query(StockArrival).options(
        joinedload(StockArrival.supplier),
        selectinload(StockArrival.lines).joinedload(StockArrivalLine.product),
    ).filter(StockArrival.enterprise_id == enterprise_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(StockArrival.name.ilike(pattern), StockArrival.reference.ilike(pattern)))
    if status_filter:
        query = query.filter(StockArrival.status == status_filter)
    rows = query.order_by(StockArrival.created_at.desc(), StockArrival.id.desc()).offset(offset).limit(limit).all()
    return [_serialize_arrival(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_arrival(
    data: StockArrivalCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    enterprise_id = actor_enterprise_id(current_user)
    _require_commerce(db, enterprise_id)
    if data.supplier_id and not db.query(Fournisseur.id).filter(
        Fournisseur.id == data.supplier_id,
        Fournisseur.enterprise_id == enterprise_id,
    ).first():
        raise HTTPException(status_code=400, detail="Fournisseur non disponible dans cette entreprise")
    arrival = StockArrival(
        enterprise_id=enterprise_id,
        user_id=actor_owner_id(current_user),
        supplier_id=data.supplier_id,
        name=data.name.strip(),
        reference=data.reference.strip() if data.reference else None,
        notes=data.notes.strip() if data.notes else None,
        created_by_name=_agent_name(current_user),
    )
    db.add(arrival)
    db.flush()
    log_action(
        db=db,
        current_user=current_user,
        action="Création d'un arrivage",
        type_entite="arrivage",
        entite_id=arrival.id,
        details=f"Brouillon « {arrival.name} » créé.",
        commit=False,
    )
    db.commit()
    db.refresh(arrival)
    return _serialize_arrival(arrival, detailed=True)


@router.get("/{arrival_id}")
def get_arrival(
    arrival_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    enterprise_id = actor_enterprise_id(current_user)
    arrival = db.query(StockArrival).options(
        joinedload(StockArrival.supplier),
        selectinload(StockArrival.lines).joinedload(StockArrivalLine.product).joinedload(Produit.categorie),
        selectinload(StockArrival.lines).selectinload(StockArrivalLine.units).joinedload(StockArrivalUnit.unit),
    ).filter(StockArrival.id == arrival_id, StockArrival.enterprise_id == enterprise_id).first()
    if not arrival:
        raise HTTPException(status_code=404, detail="Arrivage introuvable")
    return _serialize_arrival(arrival, detailed=True)


@router.post("/{arrival_id}/lines", status_code=status.HTTP_201_CREATED)
def add_arrival_line(
    arrival_id: int,
    data: StockArrivalLineCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    arrival = _arrival_or_404(db, current_user, arrival_id, lock=True)
    _assert_draft(arrival)
    if len(data.barcodes) > data.quantity:
        raise HTTPException(status_code=400, detail="Le nombre de codes-barres dépasse la quantité reçue")
    product = db.query(Produit).options(joinedload(Produit.categorie)).filter(
        Produit.id == data.product_id,
        or_(
            Produit.enterprise_id == arrival.enterprise_id,
            and_(
                Produit.enterprise_id.is_(None),
                Produit.user_id == actor_owner_id(current_user),
                bool(getattr(current_user, "active_enterprise_is_primary", False)),
            ),
        ),
        Produit.date_suppression.is_(None),
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Fiche produit introuvable dans cette entreprise")
    # Migration progressive des anciennes fiches sans entreprise : dès leur
    # première utilisation dans un arrivage principal, elles sont rattachées
    # explicitement à cette entreprise et ne pourront jamais fuiter ailleurs.
    if product.enterprise_id is None:
        product.enterprise_id = arrival.enterprise_id
    existing = db.query(StockArrivalLine).filter(
        StockArrivalLine.arrival_id == arrival.id,
        StockArrivalLine.product_id == product.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce produit figure déjà dans cet arrivage")
    if data.barcodes:
        conflict = db.query(UniteProduit.code_barre).filter(
            UniteProduit.enterprise_id == arrival.enterprise_id,
            or_(UniteProduit.code_barre.in_(data.barcodes), UniteProduit.tracabilite.in_(data.barcodes)),
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Le code {conflict[0]} existe déjà dans ce stock")
        draft_lines = db.query(StockArrivalLine.barcodes_json).filter(
            StockArrivalLine.enterprise_id == arrival.enterprise_id,
            StockArrivalLine.arrival_id != arrival.id,
        ).all()
        used = {code for (codes,) in draft_lines for code in (codes or [])}
        duplicate = next((code for code in data.barcodes if code in used), None)
        if duplicate:
            raise HTTPException(status_code=409, detail=f"Le code {duplicate} appartient déjà à un autre arrivage")
    line = StockArrivalLine(
        arrival_id=arrival.id,
        enterprise_id=arrival.enterprise_id,
        product_id=product.id,
        quantity=data.quantity,
        barcodes_json=data.barcodes,
        notes=data.notes,
    )
    db.add(line)
    arrival.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(line)
    return _serialize_line(line)


@router.delete("/{arrival_id}/lines/{line_id}")
def delete_arrival_line(
    arrival_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    arrival = _arrival_or_404(db, current_user, arrival_id, lock=True)
    _assert_draft(arrival)
    line = db.query(StockArrivalLine).filter(
        StockArrivalLine.id == line_id,
        StockArrivalLine.arrival_id == arrival.id,
    ).first()
    if not line:
        raise HTTPException(status_code=404, detail="Ligne d'arrivage introuvable")
    db.delete(line)
    arrival.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Produit retiré du brouillon"}


@router.post("/{arrival_id}/validate")
def validate_arrival(
    arrival_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    arrival = _arrival_or_404(db, current_user, arrival_id, lock=True)
    _assert_draft(arrival)
    lines = db.query(StockArrivalLine).filter(StockArrivalLine.arrival_id == arrival.id).order_by(StockArrivalLine.id).all()
    if not lines:
        raise HTTPException(status_code=400, detail="Ajoutez au moins un produit avant de valider l'arrivage")
    now = datetime.utcnow()
    try:
        for line in lines:
            product = db.query(Produit).filter(
                Produit.id == line.product_id,
                Produit.enterprise_id == arrival.enterprise_id,
                Produit.date_suppression.is_(None),
            ).with_for_update().first()
            if not product:
                raise HTTPException(status_code=409, detail="Une fiche produit de l'arrivage n'est plus disponible")
            codes = list(line.barcodes_json or [])
            if codes:
                conflict = db.query(UniteProduit.code_barre).filter(
                    UniteProduit.enterprise_id == arrival.enterprise_id,
                    or_(UniteProduit.code_barre.in_(codes), UniteProduit.tracabilite.in_(codes)),
                ).first()
                if conflict:
                    raise HTTPException(status_code=409, detail=f"Le code {conflict[0]} existe déjà. Aucun stock n'a été modifié")
            created_units = []
            for code in codes:
                unit = UniteProduit(
                    produit_id=product.id,
                    enterprise_id=arrival.enterprise_id,
                    tracabilite=code,
                    code_barre=code,
                    statut="disponible",
                    date_creation=now,
                )
                db.add(unit)
                db.flush()
                created_units.append(unit)
            for _ in range(line.quantity - len(codes)):
                created_units.append(create_generated_unit(
                    db,
                    produit_id=product.id,
                    enterprise_id=arrival.enterprise_id,
                    date_creation=now,
                ))
            for unit in created_units:
                db.add(StockArrivalUnit(
                    arrival_line_id=line.id,
                    unit_id=unit.id,
                    barcode_snapshot=unit.code_barre,
                    traceability_snapshot=unit.tracabilite,
                    created_at=now,
                ))
            product.quantite = db.query(func.count(UniteProduit.id)).filter(
                UniteProduit.produit_id == product.id,
                UniteProduit.statut == "disponible",
            ).scalar() or 0
            product.a_des_barcodes = bool(product.a_des_barcodes or codes)
            product.date_modification = now
        arrival.status = "validated"
        arrival.validated_at = now
        arrival.updated_at = now
        log_action(
            db=db,
            current_user=current_user,
            action="Validation d'un arrivage",
            type_entite="arrivage",
            entite_id=arrival.id,
            details=f"{sum(line.quantity for line in lines)} unités ajoutées au stock via « {arrival.name} ».",
            commit=False,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="L'arrivage n'a pas pu être validé. Aucun ajout partiel n'a été conservé")
    return {"message": "Arrivage validé et stock mis à jour", "arrival_id": arrival.id}


def _destination_product(db: Session, source: Produit, destination: Enterprise, owner_id: int) -> Produit:
    if not source.catalog_key:
        source.catalog_key = str(uuid4())
        db.flush()
    product = db.query(Produit).filter(
        Produit.enterprise_id == destination.id,
        Produit.catalog_key == source.catalog_key,
        Produit.date_suppression.is_(None),
    ).first()
    if product:
        return product
    category = db.query(Categorie).filter(
        Categorie.enterprise_id == destination.id,
        func.lower(Categorie.nom) == source.categorie.nom.lower(),
    ).first()
    if not category:
        category = Categorie(
            nom=source.categorie.nom,
            description=source.categorie.description,
            user_id=owner_id,
            enterprise_id=destination.id,
        )
        db.add(category)
        db.flush()
    product = Produit(
        nom=source.nom,
        categorie_id=category.id,
        prix_achat=source.prix_achat,
        prix_vente=source.prix_vente,
        quantite=0,
        rating=source.rating,
        caracteristiques=source.caracteristiques,
        couleur=source.couleur,
        etat=source.etat,
        commentaire=source.commentaire,
        is_installe=source.is_installe,
        emplacement=source.emplacement,
        image_url=source.image_url,
        stock_min=source.stock_min,
        a_des_barcodes=source.a_des_barcodes,
        catalog_key=source.catalog_key,
        user_id=owner_id,
        enterprise_id=destination.id,
    )
    db.add(product)
    db.flush()
    return product


def _perform_transfer(db: Session, actor, data: StockTransferCreate) -> StockTransfer:
    source_id = actor_enterprise_id(actor)
    source_enterprise = _require_commerce(db, source_id)
    destination = _require_commerce(db, data.destination_enterprise_id)
    if destination.id == source_id:
        raise HTTPException(status_code=400, detail="Choisissez une autre entreprise de destination")
    if destination.group_id != source_enterprise.group_id:
        raise HTTPException(status_code=403, detail="Le transfert est limité aux entreprises de votre groupe")
    if data.source_arrival_id and not db.query(StockArrival.id).filter(
        StockArrival.id == data.source_arrival_id,
        StockArrival.enterprise_id == source_id,
        StockArrival.status == "validated",
    ).first():
        raise HTTPException(status_code=404, detail="Arrivage source validé introuvable")
    transfer = StockTransfer(
        source_enterprise_id=source_id,
        destination_enterprise_id=destination.id,
        source_arrival_id=data.source_arrival_id,
        user_id=actor_owner_id(actor),
        notes=data.notes,
        created_by_name=_agent_name(actor),
    )
    db.add(transfer)
    db.flush()
    seen_products = set()
    for item in data.items:
        if item.product_id in seen_products:
            raise HTTPException(status_code=400, detail="Un produit ne peut apparaître qu'une fois dans un transfert")
        seen_products.add(item.product_id)
        source = db.query(Produit).options(joinedload(Produit.categorie)).filter(
            Produit.id == item.product_id,
            Produit.enterprise_id == source_id,
            Produit.date_suppression.is_(None),
        ).with_for_update().first()
        if not source:
            raise HTTPException(status_code=404, detail="Produit source introuvable")
        unit_query = db.query(UniteProduit).filter(
            UniteProduit.produit_id == source.id,
            UniteProduit.enterprise_id == source_id,
            UniteProduit.statut == "disponible",
            UniteProduit.commande_vente_id.is_(None),
        )
        if data.source_arrival_id:
            unit_query = unit_query.join(
                StockArrivalUnit, StockArrivalUnit.unit_id == UniteProduit.id
            ).join(
                StockArrivalLine,
                StockArrivalLine.id == StockArrivalUnit.arrival_line_id,
            ).filter(
                StockArrivalLine.arrival_id == data.source_arrival_id,
                StockArrivalLine.product_id == source.id,
            )
        if item.unit_ids:
            if len(item.unit_ids) != item.quantity or len(set(item.unit_ids)) != item.quantity:
                raise HTTPException(status_code=400, detail="La sélection des unités ne correspond pas à la quantité")
            unit_query = unit_query.filter(UniteProduit.id.in_(item.unit_ids))
        units = unit_query.order_by(UniteProduit.date_creation, UniteProduit.id).limit(item.quantity).with_for_update().all()
        if len(units) != item.quantity:
            raise HTTPException(status_code=409, detail=f"Stock disponible insuffisant pour {source.nom}")
        codes = [unit.code_barre for unit in units if unit.code_barre]
        if codes and db.query(UniteProduit.id).filter(
            UniteProduit.enterprise_id == destination.id,
            UniteProduit.code_barre.in_(codes),
        ).first():
            raise HTTPException(status_code=409, detail=f"Un code-barres de {source.nom} existe déjà dans la destination")
        target = _destination_product(db, source, destination, actor_owner_id(actor))
        line = StockTransferLine(
            transfer_id=transfer.id,
            source_product_id=source.id,
            destination_product_id=target.id,
            quantity=item.quantity,
        )
        db.add(line)
        db.flush()
        for unit in units:
            unit.produit_id = target.id
            unit.enterprise_id = destination.id
            unit.date_modification = datetime.utcnow()
            db.add(StockTransferUnit(
                transfer_line_id=line.id,
                unit_id=unit.id,
                barcode_snapshot=unit.code_barre,
                traceability_snapshot=unit.tracabilite,
            ))
        db.flush()
        source.quantite = db.query(func.count(UniteProduit.id)).filter(
            UniteProduit.produit_id == source.id,
            UniteProduit.statut == "disponible",
        ).scalar() or 0
        target.quantite = db.query(func.count(UniteProduit.id)).filter(
            UniteProduit.produit_id == target.id,
            UniteProduit.statut == "disponible",
        ).scalar() or 0
        source.date_modification = target.date_modification = datetime.utcnow()
    detail = (
        f"Transfert #{transfer.id} de {source_enterprise.name} vers {destination.name} : "
        f"{sum(item.quantity for item in data.items)} unité(s)."
    )
    log_action(
        db=db,
        current_user=actor,
        action="Transfert de stock sortant",
        type_entite="transfert_stock",
        entite_id=transfer.id,
        details=detail,
        commit=False,
    )
    is_main = bool(getattr(actor, "is_main_user", False) or getattr(actor, "is_superuser", False))
    db.add(Historique(
        action="Transfert de stock entrant",
        type_entite="transfert_stock",
        entite_id=transfer.id,
        user_id=actor_owner_id(actor),
        sub_user_id=None if is_main else actor.id,
        details=detail,
        nom_user=getattr(actor, "email", None) if is_main else None,
        nom_sub_user=None if is_main else getattr(actor, "username", None),
        enterprise_id=destination.id,
    ))
    return transfer


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def transfer_stock(
    data: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    try:
        transfer = _perform_transfer(db, current_user, data)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Le transfert a échoué. Aucun stock partiel n'a été conservé")
    return {"message": "Transfert terminé", "transfer_id": transfer.id}


@router.post("/{arrival_id}/transfer", status_code=status.HTTP_201_CREATED)
def transfer_arrival(
    arrival_id: int,
    data: ArrivalTransferCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    arrival = _arrival_or_404(db, current_user, arrival_id, lock=True)
    if arrival.status != "validated":
        raise HTTPException(status_code=409, detail="Seul un arrivage validé peut être transféré")
    items = data.items
    if not items:
        items = []
        lines = db.query(StockArrivalLine).filter(StockArrivalLine.arrival_id == arrival.id).all()
        for line in lines:
            available_ids = [row[0] for row in db.query(UniteProduit.id).join(
                StockArrivalUnit, StockArrivalUnit.unit_id == UniteProduit.id
            ).filter(
                StockArrivalUnit.arrival_line_id == line.id,
                UniteProduit.produit_id == line.product_id,
                UniteProduit.enterprise_id == arrival.enterprise_id,
                UniteProduit.statut == "disponible",
                UniteProduit.commande_vente_id.is_(None),
            ).all()]
            if available_ids:
                items.append(StockTransferItem(product_id=line.product_id, quantity=len(available_ids), unit_ids=available_ids))
    if not items:
        raise HTTPException(status_code=409, detail="Cet arrivage ne contient plus aucune unité disponible à transférer")
    payload = StockTransferCreate(
        destination_enterprise_id=data.destination_enterprise_id,
        items=items,
        notes=data.notes,
        source_arrival_id=arrival.id,
    )
    try:
        transfer = _perform_transfer(db, current_user, payload)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Le transfert de l'arrivage a échoué. Aucun mouvement partiel n'a été conservé")
    return {"message": "Arrivage transféré", "transfer_id": transfer.id}


@router.get("/products/{product_id}/movements")
def product_movements(
    product_id: int,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    enterprise_id = actor_enterprise_id(current_user)
    product = db.query(Produit).filter(
        Produit.id == product_id,
        Produit.enterprise_id == enterprise_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    events = []
    arrival_lines = db.query(StockArrivalLine).options(joinedload(StockArrivalLine.arrival)).filter(
        StockArrivalLine.product_id == product.id,
        StockArrivalLine.enterprise_id == enterprise_id,
    ).all()
    for line in arrival_lines:
        events.append({
            "type": "arrival",
            "title": f"Arrivage : {line.arrival.name}",
            "quantity": line.quantity,
            "from_enterprise": None,
            "to_enterprise": line.arrival.enterprise.name,
            "agent": line.arrival.created_by_name,
            "date": line.arrival.validated_at or line.created_at,
        })
    transfers = db.query(StockTransferLine).options(
        joinedload(StockTransferLine.transfer).joinedload(StockTransfer.source_enterprise),
        joinedload(StockTransferLine.transfer).joinedload(StockTransfer.destination_enterprise),
    ).filter(or_(
        StockTransferLine.source_product_id == product.id,
        StockTransferLine.destination_product_id == product.id,
    )).all()
    for line in transfers:
        transfer = line.transfer
        incoming = line.destination_product_id == product.id
        events.append({
            "type": "transfer_in" if incoming else "transfer_out",
            "title": "Transfert entrant" if incoming else "Transfert sortant",
            "quantity": line.quantity,
            "from_enterprise": transfer.source_enterprise.name,
            "to_enterprise": transfer.destination_enterprise.name,
            "agent": transfer.created_by_name,
            "date": transfer.created_at,
            "notes": transfer.notes,
        })
    events.sort(key=lambda event: event["date"] or datetime.min, reverse=True)
    return events[:limit]


@router.get("/products/{product_id}/arrival-units")
def product_arrival_units(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    """Suit les unités d'une fiche depuis leur arrivage, même après transfert."""
    enterprise_id = actor_enterprise_id(current_user)
    product = db.query(Produit).filter(
        Produit.id == product_id,
        Produit.enterprise_id == enterprise_id,
        Produit.date_suppression.is_(None),
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    product_ids = [product.id]
    if product.catalog_key and enterprise:
        product_ids = [row[0] for row in (
            db.query(Produit.id)
            .join(Enterprise, Enterprise.id == Produit.enterprise_id)
            .filter(
                Produit.catalog_key == product.catalog_key,
                Produit.date_suppression.is_(None),
                Enterprise.group_id == enterprise.group_id,
            )
            .all()
        )]

    lines = (
        db.query(StockArrivalLine)
        .options(
            joinedload(StockArrivalLine.arrival).joinedload(StockArrival.enterprise),
            selectinload(StockArrivalLine.units)
            .joinedload(StockArrivalUnit.unit)
            .joinedload(UniteProduit.enterprise),
            selectinload(StockArrivalLine.units)
            .joinedload(StockArrivalUnit.unit)
            .joinedload(UniteProduit.produit),
        )
        .filter(StockArrivalLine.product_id.in_(product_ids))
        .order_by(StockArrivalLine.created_at.desc(), StockArrivalLine.id.desc())
        .all()
    )

    result = []
    for line in lines:
        units = [_serialize_unit(link) for link in line.units]
        counts = {}
        for unit in units:
            normalized = (unit.get("status") or "inconnu").strip().lower().replace("_", " ")
            counts[normalized] = counts.get(normalized, 0) + 1
        result.append({
            "arrival_id": line.arrival_id,
            "arrival_name": line.arrival.name,
            "arrival_reference": line.arrival.reference,
            "source_enterprise_id": line.enterprise_id,
            "source_enterprise_name": line.arrival.enterprise.name,
            "received_quantity": line.quantity,
            "created_at": line.arrival.validated_at or line.created_at,
            "status_counts": counts,
            "units": units,
        })
    return result
