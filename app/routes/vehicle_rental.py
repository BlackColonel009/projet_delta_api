from datetime import datetime
from io import BytesIO
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.model_client import Client
from app.models.model_enterprise import Enterprise
from app.models.model_vehicle_rental import RentalVehicle, VehicleRentalCharge, VehicleRentalEvent, VehicleRentalPayment, VehicleReservation
from app.schemas.vehicle_rental_schema import (
    ReservationCreate,
    ReservationOut,
    ReservationTransition,
    RentalChargeCreate,
    RentalPaymentCreate,
    VehicleCreate,
    VehicleOut,
)
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id
from app.utils.permissions import All_required

router = APIRouter(prefix="/vehicle-rental", tags=["Location de véhicules"])

TRANSITIONS = {
    "reserved": {"confirmed", "cancelled"},
    "confirmed": {"prepared", "cancelled"},
    "prepared": {"rented", "cancelled"},
    "rented": {"return_expected", "inspection", "late", "damaged"},
    "return_expected": {"inspection", "late", "damaged"},
    "late": {"inspection", "damaged"},
    "inspection": {"completed", "damaged"},
    "damaged": {"inspection", "completed"},
    "completed": set(),
    "cancelled": set(),
}
BLOCKING_STATUSES = {"reserved", "confirmed", "prepared", "rented", "return_expected", "late"}


def _ensure_vehicle_business(actor):
    if not getattr(actor, "is_superuser", False) and getattr(actor, "active_enterprise_business_type", None) != "vehicle_rental":
        raise HTTPException(status_code=403, detail={"code": "VEHICLE_RENTAL_REQUIRED", "message": "Cette fonction est réservée à une entreprise de location de véhicules."})


def _agent(actor):
    return str(getattr(actor, "username", None) or getattr(actor, "email", None) or "Agent Trade Care"), getattr(actor, "role", None)


def _serialize(reservation):
    return {
        **{column.name: getattr(reservation, column.name) for column in VehicleReservation.__table__.columns},
        "vehicle_name": reservation.vehicle.name if reservation.vehicle else None,
        "client_name": reservation.client.nom if reservation.client else None,
    }


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), vehicle_status: str | None = Query(None, alias="status"), db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    query = db.query(RentalVehicle).filter(RentalVehicle.enterprise_id == actor_enterprise_id(current_user), RentalVehicle.is_active.is_(True))
    if vehicle_status:
        query = query.filter(RentalVehicle.status == vehicle_status)
    return query.order_by(RentalVehicle.name).offset(offset).limit(limit).all()


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    registration = data.registration_number.strip().upper()
    if db.query(RentalVehicle.id).filter(RentalVehicle.enterprise_id == enterprise_id, func.upper(RentalVehicle.registration_number) == registration).first():
        raise HTTPException(status_code=409, detail="Cette immatriculation existe déjà")
    vehicle = RentalVehicle(enterprise_id=enterprise_id, user_id=actor_owner_id(current_user), **data.model_dump(exclude={"registration_number"}), registration_number=registration)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), reservation_status: str | None = Query(None, alias="status"), search: str | None = None, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    query = db.query(VehicleReservation).options(selectinload(VehicleReservation.vehicle), selectinload(VehicleReservation.client)).filter(VehicleReservation.enterprise_id == actor_enterprise_id(current_user))
    if reservation_status:
        query = query.filter(VehicleReservation.status == reservation_status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(VehicleReservation.client).join(VehicleReservation.vehicle).filter(or_(VehicleReservation.reservation_number.ilike(pattern), Client.nom.ilike(pattern), RentalVehicle.registration_number.ilike(pattern)))
    return [_serialize(item) for item in query.order_by(VehicleReservation.start_at.desc()).offset(offset).limit(limit).all()]


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    vehicle = db.query(RentalVehicle).filter(RentalVehicle.id == data.vehicle_id, RentalVehicle.enterprise_id == enterprise_id, RentalVehicle.is_active.is_(True)).with_for_update().first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Véhicule introuvable")
    if vehicle.status in {"maintenance", "damaged", "immobilized"}:
        raise HTTPException(status_code=409, detail="Ce véhicule est indisponible")
    if not db.query(Client.id).filter(Client.id == data.client_id, Client.enterprise_id == enterprise_id).first():
        raise HTTPException(status_code=404, detail="Client introuvable")
    conflict = db.query(VehicleReservation.id).filter(
        VehicleReservation.enterprise_id == enterprise_id,
        VehicleReservation.vehicle_id == data.vehicle_id,
        VehicleReservation.status.in_(BLOCKING_STATUSES),
        VehicleReservation.start_at < data.end_at,
        VehicleReservation.end_at > data.start_at,
    ).first()
    if conflict:
        raise HTTPException(status_code=409, detail={"code": "VEHICLE_ALREADY_BOOKED", "message": "Le véhicule est déjà réservé sur cette période."})
    days = max(1, ceil((data.end_at - data.start_at).total_seconds() / 86400))
    agent_name, agent_role = _agent(current_user)
    reservation = VehicleReservation(
        enterprise_id=enterprise_id, user_id=actor_owner_id(current_user), vehicle_id=data.vehicle_id,
        client_id=data.client_id, reservation_number="PENDING", start_at=data.start_at, end_at=data.end_at,
        rate_snapshot=vehicle.daily_rate, deposit_snapshot=vehicle.deposit_amount,
        estimated_total=round(days * vehicle.daily_rate, 2), created_by_name=agent_name, created_by_role=agent_role,
    )
    db.add(reservation)
    db.flush()
    reservation.reservation_number = f"LOC-{datetime.utcnow():%Y%m%d}-{reservation.id:05d}"
    reservation.events.append(VehicleRentalEvent(to_status="reserved", note="Réservation créée", agent_name=agent_name, agent_role=agent_role))
    db.commit()
    reservation = db.query(VehicleReservation).options(selectinload(VehicleReservation.vehicle), selectinload(VehicleReservation.client)).filter(VehicleReservation.id == reservation.id).one()
    return _serialize(reservation)


@router.post("/reservations/{reservation_id}/transition", response_model=ReservationOut)
def transition_reservation(reservation_id: int, data: ReservationTransition, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    reservation = db.query(VehicleReservation).options(selectinload(VehicleReservation.vehicle), selectinload(VehicleReservation.client), selectinload(VehicleReservation.events)).filter(VehicleReservation.id == reservation_id, VehicleReservation.enterprise_id == actor_enterprise_id(current_user)).with_for_update().first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    if data.status not in TRANSITIONS.get(reservation.status, set()):
        raise HTTPException(status_code=409, detail=f"Transition impossible de {reservation.status} vers {data.status}")
    previous = reservation.status
    reservation.status = data.status
    if data.status == "rented":
        reservation.start_mileage, reservation.start_fuel_level = data.mileage, data.fuel_level
        reservation.vehicle.status = "rented"
    elif data.status in {"inspection", "completed", "damaged"}:
        reservation.end_mileage, reservation.end_fuel_level = data.mileage, data.fuel_level
        reservation.inspection_json = data.inspection
        reservation.vehicle.status = "available" if data.status == "completed" else data.status
        if data.mileage is not None:
            reservation.vehicle.mileage = data.mileage
    elif data.status == "cancelled":
        reservation.vehicle.status = "available"
    agent_name, agent_role = _agent(current_user)
    reservation.events.append(VehicleRentalEvent(from_status=previous, to_status=data.status, note=data.note, agent_name=agent_name, agent_role=agent_role))
    db.commit()
    return _serialize(reservation)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    vehicles = dict(db.query(RentalVehicle.status, func.count(RentalVehicle.id)).filter(RentalVehicle.enterprise_id == enterprise_id, RentalVehicle.is_active.is_(True)).group_by(RentalVehicle.status).all())
    reservations = dict(db.query(VehicleReservation.status, func.count(VehicleReservation.id)).filter(VehicleReservation.enterprise_id == enterprise_id).group_by(VehicleReservation.status).all())
    return {"vehicles": vehicles, "reservations": reservations, "fleet_total": sum(vehicles.values()), "available": vehicles.get("available", 0), "rented": vehicles.get("rented", 0), "maintenance": vehicles.get("maintenance", 0)}


@router.post("/reservations/{reservation_id}/payments", status_code=201)
def record_payment(reservation_id: int, data: RentalPaymentCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    reservation = db.query(VehicleReservation).filter(VehicleReservation.id == reservation_id, VehicleReservation.enterprise_id == enterprise_id).with_for_update().first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    rental_received = float(reservation.paid_amount or 0)
    deposit_held = float(reservation.deposit_paid or 0)
    if data.kind == "rental":
        remaining = round(float(reservation.estimated_total) - rental_received, 2)
        if data.amount > remaining + 0.001:
            raise HTTPException(status_code=409, detail=f"Le montant dépasse le reste à payer ({remaining:.2f})")
        reservation.paid_amount = round(rental_received + data.amount, 2)
    elif data.kind == "deposit":
        remaining = round(float(reservation.deposit_snapshot) - deposit_held, 2)
        if data.amount > remaining + 0.001:
            raise HTTPException(status_code=409, detail=f"La caution dépasse le montant prévu ({remaining:.2f})")
        reservation.deposit_paid = round(deposit_held + data.amount, 2)
    else:
        if data.amount > deposit_held + 0.001:
            raise HTTPException(status_code=409, detail="Le remboursement dépasse la caution détenue")
        reservation.deposit_paid = round(deposit_held - data.amount, 2)
    agent_name, _ = _agent(current_user)
    payment = VehicleRentalPayment(enterprise_id=enterprise_id, reservation_id=reservation.id, kind=data.kind, amount=data.amount, payment_method=data.payment_method, reference=data.reference, agent_name=agent_name)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"id": payment.id, "kind": payment.kind, "amount": payment.amount, "payment_method": payment.payment_method, "created_at": payment.created_at, "rental_paid": reservation.paid_amount, "deposit_held": reservation.deposit_paid}


@router.post("/reservations/{reservation_id}/charges", status_code=201)
def add_charge(reservation_id: int, data: RentalChargeCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    reservation = db.query(VehicleReservation).filter(VehicleReservation.id == reservation_id, VehicleReservation.enterprise_id == enterprise_id).with_for_update().first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    agent_name, _ = _agent(current_user)
    charge = VehicleRentalCharge(enterprise_id=enterprise_id, reservation_id=reservation.id, kind=data.kind, label=data.label, amount=data.amount, notes=data.notes, agent_name=agent_name)
    reservation.estimated_total = round(float(reservation.estimated_total) + data.amount, 2)
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return {"id": charge.id, "kind": charge.kind, "label": charge.label, "amount": charge.amount, "new_total": reservation.estimated_total}


@router.get("/reservations/{reservation_id}/financial-summary")
def financial_summary(reservation_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    reservation = db.query(VehicleReservation).filter(VehicleReservation.id == reservation_id, VehicleReservation.enterprise_id == enterprise_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    charges = db.query(VehicleRentalCharge).filter(VehicleRentalCharge.reservation_id == reservation.id, VehicleRentalCharge.enterprise_id == enterprise_id).order_by(VehicleRentalCharge.created_at).all()
    payments = db.query(VehicleRentalPayment).filter(VehicleRentalPayment.reservation_id == reservation.id, VehicleRentalPayment.enterprise_id == enterprise_id).order_by(VehicleRentalPayment.created_at).all()
    return {"rental_total": reservation.estimated_total, "rental_paid": reservation.paid_amount, "rental_due": max(0, reservation.estimated_total - reservation.paid_amount), "deposit_expected": reservation.deposit_snapshot, "deposit_held": reservation.deposit_paid, "charges": [{"kind": x.kind, "label": x.label, "amount": x.amount, "created_at": x.created_at} for x in charges], "payments": [{"kind": x.kind, "amount": x.amount, "payment_method": x.payment_method, "created_at": x.created_at} for x in payments]}


@router.get("/reservations/{reservation_id}/document")
def rental_document(reservation_id: int, document_type: str = Query("contract", pattern="^(booking|contract|departure|return)$"), db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure_vehicle_business(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    reservation = db.query(VehicleReservation).options(selectinload(VehicleReservation.vehicle), selectinload(VehicleReservation.client)).filter(VehicleReservation.id == reservation_id, VehicleReservation.enterprise_id == enterprise_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Réservation introuvable")
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    titles = {"booking": "BON DE RÉSERVATION", "contract": "CONTRAT DE LOCATION", "departure": "FICHE DE DÉPART", "return": "FICHE DE RETOUR"}
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    primary = colors.HexColor(getattr(enterprise, "invoice_color", None) or "#5C6BC0")
    story = [Paragraph(enterprise.name if enterprise else "Trade Care", styles["Title"]), Paragraph(titles[document_type], styles["Heading1"]), Spacer(1, 6*mm)]
    data = [
        ["Référence", reservation.reservation_number], ["Client", reservation.client.nom],
        ["Véhicule", f"{reservation.vehicle.brand} {reservation.vehicle.model}"], ["Immatriculation", reservation.vehicle.registration_number],
        ["Départ", reservation.start_at.strftime("%d/%m/%Y %H:%M")], ["Retour prévu", reservation.end_at.strftime("%d/%m/%Y %H:%M")],
        ["Tarif location", f"{reservation.estimated_total:,.0f} {getattr(enterprise, 'currency', 'XOF')}"],
        ["Caution", f"{reservation.deposit_snapshot:,.0f} {getattr(enterprise, 'currency', 'XOF')}"], ["Agent", reservation.created_by_name],
    ]
    if document_type in {"departure", "return"}:
        data.extend([["Kilométrage départ", reservation.start_mileage or "—"], ["Kilométrage retour", reservation.end_mileage or "—"], ["Carburant départ", reservation.start_fuel_level or "—"], ["Carburant retour", reservation.end_fuel_level or "—"]])
    table = Table(data, colWidths=[55*mm, 105*mm])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), primary), ("TEXTCOLOR", (0,0), (0,-1), colors.white), ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#D6DAE4")), ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), ("PADDING", (0,0), (-1,-1), 8)]))
    story.extend([table, Spacer(1, 18*mm), Paragraph("Signature du client                                         Signature de l'entreprise", styles["BodyText"])])
    doc.build(story)
    buffer.seek(0)
    filename = f"{document_type}_{reservation.reservation_number}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
