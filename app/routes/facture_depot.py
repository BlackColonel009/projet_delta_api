from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.platypus import HRFlowable, Spacer
from sqlalchemy.orm import Session, joinedload
from starlette.responses import StreamingResponse

from app.database import get_db
from app.models.model_depot import Depot
from app.models.model_facture_depot import FactureDepot
from app.schemas import facture_depot_schema as schemas
from app.services.report_design import ReportDesign, money
from app.utils.permissions import All_required
from app.utils.subscription_guard import enforce_invoice_quota

router = APIRouter(prefix="/factures-depot", tags=["Factures Dépôt"])


def _owner_id(user):
    return user.id if user.is_main_user else user.parent_user_id


def _query(db, facture_id, owner_id):
    return db.query(FactureDepot).options(
        joinedload(FactureDepot.user),
        joinedload(FactureDepot.depot).joinedload(Depot.client),
        joinedload(FactureDepot.depot).joinedload(Depot.service),
        joinedload(FactureDepot.depot).joinedload(Depot.tarif_items),
    ).filter(
        FactureDepot.id == facture_id,
        FactureDepot.user_id == owner_id,
    )


@router.post("/", response_model=schemas.FactureDepotOut)
def create_facture_depot(payload: schemas.FactureDepotCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    owner_id = _owner_id(current_user)
    enforce_invoice_quota(db, current_user)
    depot = db.query(Depot).filter(Depot.id == payload.depot_id, Depot.user_id == owner_id).first()
    if not depot:
        raise HTTPException(404, "Dépôt introuvable")
    existing = db.query(FactureDepot).filter(FactureDepot.depot_id == payload.depot_id, FactureDepot.user_id == owner_id).first()
    if existing:
        raise HTTPException(400, "Une facture existe déjà pour ce dépôt.")
    facture = FactureDepot(**payload.model_dump(exclude={"client_id"}), client_id=depot.client_id,
                           user_id=owner_id, date_facture=datetime.utcnow())
    db.add(facture)
    db.commit()
    db.refresh(facture)
    return facture


@router.get("/{id}", response_model=schemas.FactureDepotOut)
def get_facture_depot(id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, _owner_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    return facture


@router.put("/{id}", response_model=schemas.FactureDepotOut)
def update_facture_depot(id: int, payload: schemas.FactureDepotUpdate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, _owner_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(facture, attr, value)
    db.commit()
    db.refresh(facture)
    return facture


@router.delete("/{id}")
def delete_facture_depot(id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, _owner_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    db.delete(facture)
    db.commit()
    return {"detail": "Facture supprimée"}


def _document(facture, receipt):
    depot, company = facture.depot, facture.user
    design = ReportDesign(company)
    currency = getattr(company, "devise", None) or "FCFA"
    service = getattr(getattr(depot, "service", None), "nom", None) or "Service de dépôt"
    client = getattr(getattr(depot, "client", None), "nom", None) or "Client non renseigné"
    issued = facture.created_at or facture.date_facture or datetime.utcnow()
    rows, calculated_total = [], 0.0
    for item in depot.tarif_items:
        tariff = getattr(item, "tarif", None)
        label = getattr(tariff, "nom_tarif", None) or "Service"
        description = (getattr(item, "description", None) or "").strip()
        quantity = int(getattr(item, "quantite", 0) or 0)
        unit_price = float(getattr(item, "prix_personnalise", None) or getattr(tariff, "tarif_unitaire", None) or 0)
        line_total = unit_price * quantity
        calculated_total += line_total
        rows.append([f"{label} — {description}" if description else label, quantity,
                     money(unit_price, currency), money(line_total, currency)])
    title = "ACCUSÉ DE DÉPÔT" if receipt else "FACTURE DE RETRAIT"
    status = "À régler au retrait" if receipt else "Facture finale"
    story = [Spacer(1, 18), *design.logo(), design.p(design.name, "Heading1"),
             design.p(title, "Title"), HRFlowable(width="100%", thickness=3, color=design.primary, spaceAfter=16),
             design.table(["Référence", "Date d’émission", "Statut"],
                          [[f"DEP-{issued.year}-{facture.id:05d}", issued.strftime("%d/%m/%Y"), status]]),
             Spacer(1, 18), design.p("Informations du dépôt", "Heading2"),
             design.table(["Client", "Service", "Bien confié", "Date de dépôt"],
                          [[client, service, depot.description_bien, depot.date_depot.strftime("%d/%m/%Y à %H:%M")]]),
             Spacer(1, 18), design.p("Détail des prestations", "Heading2"),
             design.table(["Désignation", "Qté", "Prix unitaire", "Total"], rows, widths=[230, 48, 100, 105]),
             Spacer(1, 18), design.table(["Montant HT", "TVA", "Total TTC"],
                          [[money(facture.montant_ht, currency), money(facture.tva, currency),
                            money(facture.montant_ttc or calculated_total, currency)]]),
             Spacer(1, 24), design.p("Ce document confirme la prise en charge du bien. Conservez sa référence pour tout suivi."
                                     if receipt else "Merci pour votre confiance. Cette facture clôture les prestations du dépôt.")]
    buffer = BytesIO()
    design.build(buffer, story, pagesize=A4)
    return buffer


def _response(facture, receipt):
    prefix = "accuse_depot" if receipt else "facture_retrait"
    return StreamingResponse(_document(facture, receipt), media_type="application/pdf",
                             headers={"Content-Disposition": f"inline; filename={prefix}_{facture.id}.pdf"})


@router.get("/{facture_id}/preview")
def preview_final_invoice(facture_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, facture_id, _owner_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture de dépôt non trouvée")
    return _response(facture, False)


@router.get("/{facture_id}/depot-preview")
def preview_deposit_receipt(facture_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, facture_id, _owner_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture de dépôt non trouvée")
    return _response(facture, True)
