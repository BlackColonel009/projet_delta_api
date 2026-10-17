from datetime import datetime
from html import escape
from io import BytesIO
import os
import tempfile
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from reportlab.lib.pagesizes import A4
from reportlab.platypus import HRFlowable, Spacer
from sqlalchemy.orm import Session, joinedload
from starlette.responses import StreamingResponse

from app.database import get_db
from app.core.mail import send_email_message
from app.models.model_depot import Depot
from app.models.model_facture_depot import FactureDepot
from app.schemas import facture_depot_schema as schemas
from app.services.report_design import ReportDesign, money
from app.services.depot_workflow_service import (
    InvalidDepositTransition,
    validate_deposit_transition,
)
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.utils.permissions import All_required, check_role
from app.utils.subscription_guard import enforce_feature_access, enforce_invoice_quota
from app.utils.i18n import language_of, translated
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter
from app.services.invoice_snapshot_service import (
    invoice_snapshot_values,
    validate_official_invoice_date,
)

router = APIRouter(prefix="/factures-depot", tags=["Factures Dépôt"])


def _owner_id(user):
    return actor_owner_id(user)


def _query(db, facture_id, enterprise_id):
    return db.query(FactureDepot).options(
        joinedload(FactureDepot.user),
        joinedload(FactureDepot.depot).joinedload(Depot.client),
        joinedload(FactureDepot.depot).joinedload(Depot.service),
        joinedload(FactureDepot.depot).joinedload(Depot.tarif_items),
    ).filter(
        FactureDepot.id == facture_id,
        FactureDepot.enterprise_id == enterprise_id,
    )


@router.post("/", response_model=schemas.FactureDepotOut)
def create_facture_depot(payload: schemas.FactureDepotCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    owner_id = _owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    enforce_invoice_quota(db, current_user)
    depot = db.query(Depot).filter(Depot.id == payload.depot_id, enterprise_scope_filter(Depot, current_user)).first()
    if not depot:
        raise HTTPException(404, "Dépôt introuvable")
    existing = db.query(FactureDepot).filter(FactureDepot.depot_id == payload.depot_id, FactureDepot.enterprise_id == enterprise_id).first()
    if existing:
        raise HTTPException(400, "Une facture existe déjà pour ce dépôt.")
    montant_ht = round(float(depot.prix_total or 0), 2)
    facture = FactureDepot(
        depot_id=depot.id,
        client_id=depot.client_id,
        montant_ht=montant_ht,
        tva=0,
        montant_ttc=montant_ht,
        statut="en_attente",
        remarques=payload.remarques,
        user_id=owner_id,
        enterprise_id=enterprise_id,
        date_facture=validate_official_invoice_date(payload.invoice_date),
        **invoice_snapshot_values(db, current_user, enterprise_id),
    )
    db.add(facture)
    db.commit()
    db.refresh(facture)
    return facture


@router.get("/{id}", response_model=schemas.FactureDepotOut)
def get_facture_depot(id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    return facture


@router.put("/{id}", response_model=schemas.FactureDepotOut)
def update_facture_depot(id: int, payload: schemas.FactureDepotUpdate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(facture, attr, value)
    db.commit()
    db.refresh(facture)
    return facture


@router.put("/{id}/payer", response_model=schemas.FactureDepotOut)
def payer_facture_depot(
    id: int,
    payload: schemas.FactureDepotPaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable])
    ),
):
    owner_id = _owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    facture = (
        db.query(FactureDepot)
        .filter(
            FactureDepot.id == id,
            enterprise_scope_filter(FactureDepot, current_user),
        )
        .with_for_update()
        .first()
    )
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    if facture.statut in {"paye", "payee", "soldee"}:
        raise HTTPException(409, "Cette facture de dépôt est déjà soldée.")
    if facture.statut in {"annule", "annulee"}:
        raise HTTPException(409, "Une facture annulée ne peut pas être payée.")
    depot = facture.depot
    try:
        validate_deposit_transition(depot.statut, "paye")
    except InvalidDepositTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    now = datetime.utcnow()
    facture.statut = "payee"
    facture.mode_paiement = payload.mode_paiement.strip()
    facture.date_paiement = now
    if payload.remarques is not None:
        facture.remarques = payload.remarques.strip() or None
    depot.statut = "paye"
    depot.statut_modifie_le = now
    depot.statut_modifie_par = current_user.id
    try:
        log_action(
            db=db,
            current_user=current_user,
            action="Paiement facture de consigne",
            type_entite="facture_depot",
            entite_id=facture.id,
            details=(
                f"Facture soldée par {facture.mode_paiement}; "
                f"montant={facture.montant_ttc}"
            ),
            commit=False,
        )
        db.commit()
        db.refresh(facture)
    except Exception:
        db.rollback()
        raise
    return facture


@router.delete("/{id}")
def delete_facture_depot(id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    facture = _query(db, id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture non trouvée")
    db.delete(facture)
    db.commit()
    return {"detail": "Facture supprimée"}


def _document(
    facture,
    receipt,
    language_user=None,
    invoice_format: Literal["simple", "professional"] = "simple",
):
    depot, company = facture.depot, facture.user
    language = language_of(language_user or company)
    tr = lambda fr, en: translated(language, fr, en)
    template_code = (
        facture.professional_template_snapshot
        if invoice_format == "professional"
        else facture.simple_template_snapshot
    ) or (
        "professional_signature"
        if invoice_format == "professional"
        else "simple_classic"
    )
    design = ReportDesign(
        company,
        primary_color=(
            facture.invoice_color_snapshot
            or getattr(company, "facture_color", None)
        ),
        document_template=template_code,
    )
    currency = getattr(company, "devise", None) or "FCFA"
    service = getattr(getattr(depot, "service", None), "nom", None) or tr("Service de dépôt", "Deposit service")
    client = getattr(getattr(depot, "client", None), "nom", None) or tr("Client non renseigné", "Customer not provided")
    issued = facture.date_facture or facture.created_at or datetime.utcnow()
    issuer = facture.issuer_name_snapshot or getattr(company, "username", None) or company.email
    issuer_role = facture.issuer_role_snapshot or tr("Propriétaire", "Owner")
    rows, calculated_total = [], 0.0
    for item in depot.tarif_items:
        tariff = getattr(item, "tarif", None)
        label = getattr(tariff, "nom_tarif", None) or tr("Service", "Service")
        description = (getattr(item, "description", None) or "").strip()
        quantity = int(getattr(item, "quantite", 0) or 0)
        mode = getattr(item, "mode_tarification_snapshot", None) or getattr(
            tariff, "mode_tarification", "unitaire"
        )
        unit_price = float(
            getattr(item, "prix_unitaire_snapshot", None)
            or getattr(item, "prix_personnalise", None)
            or (
                getattr(tariff, "tarif_par_minute", None)
                if mode in {"duree", "durée", "minute", "minutes"}
                else getattr(tariff, "tarif_unitaire", None)
            )
            or 0
        )
        stored_total = getattr(item, "montant_total", None)
        line_total = (
            float(stored_total)
            if stored_total is not None
            else unit_price * quantity
        )
        calculated_total += line_total
        if mode in {"duree", "durée", "minute", "minutes"}:
            label = f"{label} ({tr('par minute', 'per minute')})"
        rows.append([f"{label} — {description}" if description else label, quantity,
                     money(unit_price, currency), money(line_total, currency)])
    title = tr("ACCUSÉ DE DÉPÔT", "DEPOSIT RECEIPT") if receipt else tr("FACTURE DE RETRAIT", "COLLECTION INVOICE")
    status = tr("À régler au retrait", "Payable on collection") if receipt else tr("Facture finale", "Final invoice")
    reference = f"DEP-{issued.year}-{facture.id:05d}"
    totals = design.table(
        [tr("Montant HT", "Subtotal"), tr("TVA", "VAT"), tr("Total TTC", "Total incl. tax")],
        [[money(facture.montant_ht, currency), money(facture.tva, currency),
          money(facture.montant_ttc or calculated_total, currency)]],
    )
    details = design.table(
        [tr("Désignation", "Description"), tr("Qté", "Qty"),
         tr("Prix unitaire", "Unit price"), "Total"],
        rows,
        widths=[230, 48, 100, 105],
    )
    if invoice_format == "professional":
        story = [
            Spacer(1, 18),
            *design.logo(),
            design.p(design.name, "Heading1"),
            design.p(title, "Title"),
            HRFlowable(
                width="100%",
                thickness=3,
                color=design.primary,
                spaceAfter=16,
            ),
            design.table(
                [tr("Référence", "Reference"), tr("Date d’émission", "Issue date"), tr("Statut", "Status")],
                [[reference, issued.strftime("%d/%m/%Y"), status]],
            ),
            Spacer(1, 18),
            design.p(tr("Informations du dépôt", "Deposit information"), "Heading2"),
            design.table(
                [tr("Client", "Customer"), tr("Service", "Service"),
                 tr("Bien confié", "Deposited item"), tr("Date de dépôt", "Deposit date")],
                [[client, service, depot.description_bien,
                  depot.date_depot.strftime("%d/%m/%Y à %H:%M")]],
            ),
            Spacer(1, 18),
            design.p(tr("Détail des prestations", "Service details"), "Heading2"),
            details,
            Spacer(1, 18),
            totals,
        ]
    else:
        story = [
            Spacer(1, 12),
            design.p(title, "Heading1"),
            HRFlowable(
                width="100%",
                thickness=1,
                color=design.primary,
                spaceAfter=12,
            ),
            design.p(f"{design.name} · {reference}"),
            design.p(
                f"{tr('Client', 'Customer')} : {client} · "
                f"{tr('Date', 'Date')} : {issued.strftime('%d/%m/%Y')}"
            ),
            design.p(
                f"{tr('Bien', 'Item')} : {depot.description_bien} · "
                f"{tr('Service', 'Service')} : {service}"
            ),
            Spacer(1, 12),
            details,
            Spacer(1, 14),
            totals,
        ]
    story += [
        Spacer(1, 24),
        design.p(
            f"{tr('Émise par', 'Issued by')} : {issuer} · {issuer_role}"
        ),
        design.p(
            tr(
                "Ce document confirme la prise en charge du bien. Conservez sa référence pour tout suivi.",
                "This document confirms receipt of the item. Keep its reference for any follow-up.",
            )
            if receipt
            else tr(
                "Merci pour votre confiance. Cette facture clôture les prestations du dépôt.",
                "Thank you for your trust. This invoice closes the deposit services.",
            )
        ),
    ]
    buffer = BytesIO()
    design.build(buffer, story, pagesize=A4)
    return buffer


def _response(facture, receipt, language_user=None, invoice_format="simple"):
    prefix = "accuse_depot" if receipt else "facture_retrait"
    return StreamingResponse(
        _document(facture, receipt, language_user, invoice_format),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"inline; filename={prefix}_{invoice_format}_{facture.id}.pdf"
            )
        },
    )


@router.get("/{facture_id}/preview")
def preview_final_invoice(
    facture_id: int,
    invoice_format: Literal["simple", "professional"] = Query("simple"),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    facture = _query(db, facture_id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture de dépôt non trouvée")
    if invoice_format == "professional":
        enforce_feature_access(db, current_user, "professional_invoice")
    return _response(facture, False, current_user, invoice_format)


@router.get("/{facture_id}/depot-preview")
def preview_deposit_receipt(
    facture_id: int,
    invoice_format: Literal["simple", "professional"] = Query("simple"),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    facture = _query(db, facture_id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture de dépôt non trouvée")
    if invoice_format == "professional":
        enforce_feature_access(db, current_user, "professional_invoice")
    return _response(facture, True, current_user, invoice_format)


@router.post("/{facture_id}/email-client")
async def email_facture_depot(
    facture_id: int,
    invoice_format: Literal["simple", "professional"] = Query("simple"),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    facture = _query(db, facture_id, actor_enterprise_id(current_user)).first()
    if not facture:
        raise HTTPException(404, "Facture de dépôt non trouvée")
    client = getattr(facture.depot, "client", None)
    if not client or not getattr(client, "email", None):
        raise HTTPException(400, "Le client n'a pas d'adresse e-mail.")
    if invoice_format == "professional":
        enforce_feature_access(db, current_user, "professional_invoice")

    company = facture.user
    language = language_of(current_user)
    tr = lambda fr, en: translated(language, fr, en)
    pdf_buffer = _document(
        facture,
        False,
        current_user,
        invoice_format,
    )
    color = escape(
        facture.invoice_color_snapshot
        or getattr(company, "facture_color", None)
        or "#5C6BC0"
    )
    company_name = escape(
        getattr(company, "societe_ou_entreprise", None) or "Trade Care"
    )
    client_name = escape(getattr(client, "nom", None) or tr("Client", "Customer"))
    body = f"""
    <div style="background:#f4f6f8;padding:28px;font-family:Arial,sans-serif;color:#243043">
      <div style="max-width:640px;margin:auto;background:#fff;border-radius:18px;overflow:hidden;border:1px solid #e3e8ef">
        <div style="background:{color};padding:24px;color:#fff">
          <div style="font-size:13px;letter-spacing:1px;text-transform:uppercase">{company_name}</div>
          <h1 style="margin:8px 0 0;font-size:24px">{tr('Votre facture de consigne', 'Your deposit invoice')}</h1>
        </div>
        <div style="padding:26px;line-height:1.6">
          <p>{tr('Bonjour', 'Hello')} {client_name},</p>
          <p>{tr('Veuillez trouver en pièce jointe la facture correspondant au bien confié à notre service.', 'Please find attached the invoice for the item entrusted to our service.')}</p>
          <div style="border-left:4px solid {color};background:#f8fafc;padding:14px 16px;margin:20px 0">
            <strong>{tr('Référence', 'Reference')} :</strong> DEP-{facture.date_facture.year}-{facture.id:05d}<br>
            <strong>{tr('Montant', 'Amount')} :</strong> {escape(money(facture.montant_ttc, getattr(company, 'devise', None) or 'FCFA'))}
          </div>
          <p>{tr('Merci pour votre confiance.', 'Thank you for your trust.')}</p>
        </div>
        <div style="padding:16px 26px;background:#f8fafc;font-size:12px;color:#667085">{tr('Document généré par Trade Care', 'Document generated by Trade Care')}</div>
      </div>
    </div>
    """
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            prefix=f"facture_consigne_{facture.id}_",
            delete=False,
        ) as output:
            output.write(pdf_buffer.getvalue())
            path = output.name
        sent = await send_email_message(
            to_email=client.email,
            subject=tr(
                f"Votre facture de consigne #{facture.id}",
                f"Your deposit invoice #{facture.id}",
            ),
            body=body,
            reply_to=getattr(company, "email", None),
            attachments=[path],
            is_html=True,
        )
        if not sent:
            raise HTTPException(503, "L'envoi d'e-mails est désactivé.")
    finally:
        if path and os.path.exists(path):
            os.remove(path)

    log_action(
        db=db,
        current_user=current_user,
        action="Envoi facture de consigne",
        type_entite="facture_depot",
        entite_id=facture.id,
        details=f"Format={invoice_format}; destinataire={client.email}",
    )
    return {"message": tr("Facture envoyée au client.", "Invoice sent to customer.")}
