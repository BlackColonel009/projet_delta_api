from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.model_client import Client
from app.models.model_enterprise import Enterprise
from app.models.model_laundry import (
    LaundryItem,
    LaundryOrder,
    LaundryOrderEvent,
    LaundryPayment,
    LaundryService,
)
from app.schemas.laundry_schema import (
    LaundryOrderCreate,
    LaundryOrderOut,
    LaundryPaymentCreate,
    LaundryServiceCreate,
    LaundryServiceOut,
    LaundryTransition,
)
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id
from app.utils.permissions import All_required


router = APIRouter(prefix="/laundry", tags=["Pressing et blanchisserie"])

TRANSITIONS = {
    "received": {"sorted", "processing", "cancelled", "incident"},
    "sorted": {"processing", "cancelled", "incident"},
    "processing": {"drying", "ironing", "ready", "incident"},
    "drying": {"ironing", "ready", "incident"},
    "ironing": {"ready", "incident"},
    "ready": {"delivered", "incident"},
    "incident": {"processing", "ready", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


def _ensure_laundry(actor):
    if getattr(actor, "is_superuser", False):
        return
    if getattr(actor, "active_enterprise_business_type", None) != "laundry":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "LAUNDRY_BUSINESS_REQUIRED",
                "message": "Cette fonction est réservée à une entreprise de Pressing.",
            },
        )


def _agent(actor) -> tuple[str, str | None]:
    name = (
        getattr(actor, "username", None)
        or getattr(actor, "nom", None)
        or getattr(actor, "email", None)
        or "Agent Trade Care"
    )
    return str(name), getattr(actor, "role", None)


def _serialize_order(order: LaundryOrder) -> dict:
    return {
        **{column.name: getattr(order, column.name) for column in LaundryOrder.__table__.columns},
        "client_name": getattr(order.client, "nom", None) or getattr(order.client, "name", None),
        "items": order.items,
        "events": order.events,
    }


@router.get("/services", response_model=list[LaundryServiceOut])
def list_services(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    query = db.query(LaundryService).filter(
        LaundryService.enterprise_id == actor_enterprise_id(current_user)
    )
    if active_only:
        query = query.filter(LaundryService.is_active.is_(True))
    return query.order_by(LaundryService.name).all()


@router.post("/services", response_model=LaundryServiceOut, status_code=201)
def create_service(
    data: LaundryServiceCreate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    duplicate = db.query(LaundryService.id).filter(
        LaundryService.enterprise_id == enterprise_id,
        func.lower(LaundryService.name) == data.name.strip().lower(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Cette prestation existe déjà")
    service = LaundryService(
        enterprise_id=enterprise_id,
        user_id=actor_owner_id(current_user),
        **data.model_dump(),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.post("/orders", response_model=LaundryOrderOut, status_code=201)
def create_order(
    data: LaundryOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    client = db.query(Client).filter(
        Client.id == data.client_id,
        Client.enterprise_id == enterprise_id,
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable dans cette entreprise")
    service_ids = {item.service_id for item in data.items}
    services = db.query(LaundryService).filter(
        LaundryService.id.in_(service_ids),
        LaundryService.enterprise_id == enterprise_id,
        LaundryService.is_active.is_(True),
    ).all()
    by_id = {service.id: service for service in services}
    if set(by_id) != service_ids:
        raise HTTPException(status_code=400, detail="Une prestation de pressing est invalide")

    agent_name, agent_role = _agent(current_user)
    order = LaundryOrder(
        enterprise_id=enterprise_id,
        user_id=actor_owner_id(current_user),
        client_id=data.client_id,
        order_number="PENDING",
        priority=data.priority,
        due_at=data.due_at,
        notes=data.notes,
        discount=data.discount,
        created_by_name=agent_name,
        created_by_role=agent_role,
    )
    db.add(order)
    db.flush()
    order.order_number = f"PRS-{datetime.utcnow():%Y%m%d}-{order.id:05d}"
    subtotal = 0.0
    for item_data in data.items:
        service = by_id[item_data.service_id]
        unit_price = item_data.unit_price if item_data.unit_price is not None else service.unit_price
        line_total = round(float(unit_price) * item_data.quantity, 2)
        subtotal += line_total
        order.items.append(
            LaundryItem(
                service_id=service.id,
                category=item_data.category.strip(),
                description=item_data.description,
                quantity=item_data.quantity,
                unit_price_snapshot=unit_price,
                line_total=line_total,
                condition_notes=item_data.condition_notes,
                options_json=item_data.options,
            )
        )
    order.subtotal = round(subtotal, 2)
    order.total = round(max(0, subtotal - data.discount), 2)
    order.events.append(
        LaundryOrderEvent(
            from_status=None,
            to_status="received",
            note="Commande de pressing reçue",
            agent_name=agent_name,
            agent_role=agent_role,
        )
    )
    db.commit()
    order = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items),
        selectinload(LaundryOrder.events),
    ).filter(LaundryOrder.id == order.id).one()
    return _serialize_order(order)


@router.post("/orders/{order_id}/payment", response_model=LaundryOrderOut)
def record_payment(
    order_id: int,
    data: LaundryPaymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    order = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items),
        selectinload(LaundryOrder.events),
    ).filter(
        LaundryOrder.id == order_id,
        LaundryOrder.enterprise_id == actor_enterprise_id(current_user),
    ).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande de pressing introuvable")
    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="Une commande annulée ne peut pas être encaissée")
    remaining = round(float(order.total) - float(order.paid_amount), 2)
    if data.amount > remaining + 0.001:
        raise HTTPException(
            status_code=409,
            detail=f"Le montant dépasse le reste à payer ({remaining:.2f})",
        )
    order.paid_amount = round(float(order.paid_amount) + data.amount, 2)
    agent_name, agent_role = _agent(current_user)
    db.add(
        LaundryPayment(
            enterprise_id=order.enterprise_id,
            order_id=order.id,
            amount=data.amount,
            agent_name=agent_name,
        )
    )
    order.events.append(
        LaundryOrderEvent(
            from_status=order.status,
            to_status=order.status,
            note=f"Paiement enregistré : {data.amount:.2f}",
            agent_name=agent_name,
            agent_role=agent_role,
        )
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.get("/orders", response_model=list[LaundryOrderOut])
def list_orders(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    order_status: str | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=120),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    query = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items),
    ).filter(LaundryOrder.enterprise_id == actor_enterprise_id(current_user))
    if order_status:
        query = query.filter(LaundryOrder.status == order_status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(LaundryOrder.client).filter(
            or_(LaundryOrder.order_number.ilike(pattern), Client.nom.ilike(pattern))
        )
    orders = query.order_by(LaundryOrder.received_at.desc(), LaundryOrder.id.desc()).offset(offset).limit(limit).all()
    return [_serialize_order(order) for order in orders]


@router.get("/orders/{order_id}", response_model=LaundryOrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    order = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items),
        selectinload(LaundryOrder.events),
    ).filter(
        LaundryOrder.id == order_id,
        LaundryOrder.enterprise_id == actor_enterprise_id(current_user),
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande de pressing introuvable")
    return _serialize_order(order)


@router.post("/orders/{order_id}/transition", response_model=LaundryOrderOut)
def transition_order(
    order_id: int,
    data: LaundryTransition,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    order = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items),
        selectinload(LaundryOrder.events),
    ).filter(
        LaundryOrder.id == order_id,
        LaundryOrder.enterprise_id == actor_enterprise_id(current_user),
    ).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande de pressing introuvable")
    if data.status not in TRANSITIONS.get(order.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Transition impossible de {order.status} vers {data.status}",
        )
    previous = order.status
    order.status = data.status
    now = datetime.utcnow()
    if data.status == "ready":
        order.ready_at = now
    elif data.status == "delivered":
        order.delivered_at = now
    elif data.status == "cancelled":
        order.cancelled_at = now
    for item in order.items:
        item.status = data.status
    agent_name, agent_role = _agent(current_user)
    order.events.append(
        LaundryOrderEvent(
            from_status=previous,
            to_status=data.status,
            note=data.note,
            agent_name=agent_name,
            agent_role=agent_role,
        )
    )
    db.commit()
    db.refresh(order)
    return _serialize_order(order)


@router.get("/dashboard", response_model=dict)
def laundry_dashboard(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    _ensure_laundry(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    rows = db.query(LaundryOrder.status, func.count(LaundryOrder.id)).filter(
        LaundryOrder.enterprise_id == enterprise_id
    ).group_by(LaundryOrder.status).all()
    statuses = {name: int(total) for name, total in rows}
    revenue, outstanding = db.query(
        func.coalesce(func.sum(LaundryOrder.paid_amount), 0),
        func.coalesce(func.sum(LaundryOrder.total - LaundryOrder.paid_amount), 0),
    ).filter(
        LaundryOrder.enterprise_id == enterprise_id,
        LaundryOrder.status != "cancelled",
    ).one()
    return {
        "statuses": statuses,
        "active_orders": sum(
            statuses.get(value, 0)
            for value in ("received", "sorted", "processing", "drying", "ironing")
        ),
        "ready_orders": statuses.get("ready", 0),
        "late_orders": db.query(func.count(LaundryOrder.id)).filter(
            LaundryOrder.enterprise_id == enterprise_id,
            LaundryOrder.due_at < datetime.utcnow(),
            LaundryOrder.status.notin_(("ready", "delivered", "cancelled")),
        ).scalar() or 0,
        "received_amount": float(revenue or 0),
        "outstanding_amount": float(outstanding or 0),
    }


@router.get("/orders/{order_id}/document")
def laundry_document(
    order_id: int,
    document_type: str = Query("invoice", pattern="^(invoice|receipt)$"),
    template: str = Query("professional", pattern="^(simple|professional)$"),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    """Produce a service invoice or a paid receipt without creating duplicate stock/accounting rows."""
    _ensure_laundry(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    order = db.query(LaundryOrder).options(
        selectinload(LaundryOrder.client),
        selectinload(LaundryOrder.items).selectinload(LaundryItem.service),
    ).filter(
        LaundryOrder.id == order_id,
        LaundryOrder.enterprise_id == enterprise_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Commande de pressing introuvable")
    if document_type == "receipt" and float(order.total) - float(order.paid_amount) > 0.01:
        raise HTTPException(
            status_code=409,
            detail="Le reçu définitif est disponible uniquement lorsque la commande est soldée",
        )

    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    currency = getattr(enterprise, "currency", None) or "XOF"
    accent = colors.HexColor(getattr(enterprise, "invoice_color", None) or "#5C6BC0")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="LaundryMuted",
        parent=styles["BodyText"],
        textColor=colors.HexColor("#687084"),
        fontSize=9,
        leading=13,
    ))
    styles.add(ParagraphStyle(
        name="LaundryRight",
        parent=styles["BodyText"],
        alignment=2,
        fontSize=9,
    ))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"{document_type} {order.order_number}",
    )
    title = "REÇU DE PAIEMENT" if document_type == "receipt" else "FACTURE DE PRESSING"
    story = []
    if template == "professional":
        company = [
            Paragraph(f"<b>{getattr(enterprise, 'name', None) or 'Trade Care'}</b>", styles["Title"]),
            Paragraph(getattr(enterprise, "address", None) or "", styles["LaundryMuted"]),
            Paragraph(" · ".join(filter(None, [getattr(enterprise, "phone", None), getattr(enterprise, "email", None)])), styles["LaundryMuted"]),
        ]
        heading = [
            Paragraph(f"<font color='#{accent.hexval()[2:]}'><b>{title}</b></font>", styles["Heading1"]),
            Paragraph(order.order_number, styles["LaundryRight"]),
            Paragraph(order.received_at.strftime("%d/%m/%Y %H:%M"), styles["LaundryRight"]),
        ]
        header = Table([[company, heading]], colWidths=[105 * mm, 65 * mm])
        header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([header, Spacer(1, 8 * mm)])
    else:
        story.extend([
            Paragraph(title, styles["Heading1"]),
            Paragraph(f"{order.order_number} · {order.received_at:%d/%m/%Y}", styles["LaundryMuted"]),
            Spacer(1, 6 * mm),
        ])

    client_rows = [
        ["Client", getattr(order.client, "nom", None) or "Client"],
        ["Téléphone", getattr(order.client, "telephone", None) or "—"],
        ["Statut", order.status],
        ["Agent", order.created_by_name],
    ]
    client_table = Table(client_rows, colWidths=[42 * mm, 128 * mm])
    client_table.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F8FB")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#687084")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([client_table, Spacer(1, 7 * mm)])

    lines = [["Prestation / article", "Qté", "P.U.", "Total"]]
    for item in order.items:
        service_name = item.service.name if item.service else "Prestation"
        description = item.category
        if item.description:
            description = f"{description}<br/><font color='#687084'>{item.description}</font>"
        lines.append([
            Paragraph(f"<b>{service_name}</b><br/>{description}", styles["BodyText"]),
            str(item.quantity),
            f"{item.unit_price_snapshot:,.0f}",
            f"{item.line_total:,.0f}",
        ])
    lines_table = Table(lines, colWidths=[90 * mm, 18 * mm, 30 * mm, 32 * mm], repeatRows=1)
    lines_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D8DCE6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([lines_table, Spacer(1, 6 * mm)])

    balance = max(float(order.total) - float(order.paid_amount), 0)
    totals = Table([
        ["Sous-total", f"{order.subtotal:,.0f} {currency}"],
        ["Remise", f"{order.discount:,.0f} {currency}"],
        ["Total", f"{order.total:,.0f} {currency}"],
        ["Payé", f"{order.paid_amount:,.0f} {currency}"],
        ["Reste à payer", f"{balance:,.0f} {currency}"],
    ], colWidths=[42 * mm, 42 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (-1, 2), accent),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.white),
        ("LINEABOVE", (0, -1), (-1, -1), .6, colors.HexColor("#D8DCE6")),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([
        totals,
        Spacer(1, 12 * mm),
        Paragraph("Merci pour votre confiance.", styles["LaundryMuted"]),
        Paragraph("Signature du client                                      Signature de l’entreprise", styles["BodyText"]),
    ])
    doc.build(story)
    buffer.seek(0)
    filename = f"{document_type}_{order.order_number}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
