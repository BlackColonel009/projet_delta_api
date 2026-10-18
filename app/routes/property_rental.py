from calendar import monthrange
from datetime import datetime
from math import ceil
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from app.database import get_db
from app.models.model_client import Client
from app.models.model_enterprise import Enterprise
from app.models.model_property_rental import PropertyInspection, PropertyMaintenance, PropertyOccupancy, PropertyPayment, PropertyPaymentDue, PropertyUnit, RentalProperty
from app.schemas.property_rental_schema import OccupancyCreate, PropertyCreate, PropertyInspectionCreate, PropertyMaintenanceCreate, PropertyMaintenanceUpdate, PropertyPaymentCreate, PropertyReminderSettings, PropertyUnitCreate
from app.services.property_reminder_service import dispatch_property_reminders, reminder_settings, save_reminder_settings
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id
from app.utils.permissions import All_required

router = APIRouter(prefix="/property-rental", tags=["Location immobilière"])
BLOCKING_STATUSES = {"reserved", "active", "late"}


def _ensure(actor):
    if not getattr(actor, "is_superuser", False) and getattr(actor, "active_enterprise_business_type", None) != "property_rental":
        raise HTTPException(status_code=403, detail={"code": "PROPERTY_RENTAL_REQUIRED", "message": "Cette fonction est réservée à une entreprise immobilière."})


def _agent(actor):
    return str(getattr(actor, "username", None) or getattr(actor, "email", None) or "Agent Trade Care")


def _add_month(value, count, billing_day):
    month_index = value.month - 1 + count
    year, month = value.year + month_index // 12, month_index % 12 + 1
    return value.replace(year=year, month=month, day=min(billing_day, monthrange(year, month)[1]))


@router.post("/properties", status_code=201)
def create_property(data: PropertyCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user)
    item = RentalProperty(enterprise_id=actor_enterprise_id(current_user), user_id=actor_owner_id(current_user), **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"id": item.id, "name": item.name, "property_type": item.property_type, "address": item.address}


@router.get("/properties")
def list_properties(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user)
    items = db.query(RentalProperty).options(selectinload(RentalProperty.units)).filter(RentalProperty.enterprise_id == actor_enterprise_id(current_user), RentalProperty.is_active.is_(True)).order_by(RentalProperty.name).offset(offset).limit(limit).all()
    return [{"id": x.id, "name": x.name, "property_type": x.property_type, "address": x.address, "units": [{"id": u.id, "code": u.code, "name": u.name, "status": u.status, "rental_mode": u.rental_mode, "monthly_rate": u.monthly_rate, "nightly_rate": u.nightly_rate} for u in x.units]} for x in items]


@router.post("/units", status_code=201)
def create_unit(data: PropertyUnitCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    if not db.query(RentalProperty.id).filter(RentalProperty.id == data.property_id, RentalProperty.enterprise_id == enterprise_id).first():
        raise HTTPException(status_code=404, detail="Bien immobilier introuvable")
    if db.query(PropertyUnit.id).filter(PropertyUnit.property_id == data.property_id, func.lower(PropertyUnit.code) == data.code.strip().lower()).first():
        raise HTTPException(status_code=409, detail="Ce code d'unité existe déjà dans ce bien")
    unit = PropertyUnit(enterprise_id=enterprise_id, **data.model_dump())
    db.add(unit); db.commit(); db.refresh(unit)
    return {"id": unit.id, "code": unit.code, "name": unit.name, "status": unit.status}


@router.post("/occupancies", status_code=201)
def create_occupancy(data: OccupancyCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    unit = db.query(PropertyUnit).filter(PropertyUnit.id == data.unit_id, PropertyUnit.enterprise_id == enterprise_id).with_for_update().first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unité introuvable")
    if not db.query(Client.id).filter(Client.id == data.client_id, Client.enterprise_id == enterprise_id).first():
        raise HTTPException(status_code=404, detail="Locataire introuvable")
    overlap = db.query(PropertyOccupancy.id).filter(PropertyOccupancy.enterprise_id == enterprise_id, PropertyOccupancy.unit_id == unit.id, PropertyOccupancy.status.in_(BLOCKING_STATUSES), PropertyOccupancy.start_at < (data.end_at or datetime.max), (PropertyOccupancy.end_at.is_(None) | (PropertyOccupancy.end_at > data.start_at))).first()
    if overlap:
        raise HTTPException(status_code=409, detail={"code": "UNIT_ALREADY_OCCUPIED", "message": "Cette unité est déjà réservée ou louée sur cette période."})
    rate = unit.nightly_rate if data.occupancy_type == "stay" else unit.monthly_rate
    if rate is None:
        raise HTTPException(status_code=409, detail="Aucun tarif compatible n'est configuré pour cette unité")
    count = max(1, ceil(((data.end_at - data.start_at).total_seconds() / 86400))) if data.occupancy_type == "stay" else 1
    total = round(rate * count, 2)
    item = PropertyOccupancy(enterprise_id=enterprise_id, user_id=actor_owner_id(current_user), unit_id=unit.id, client_id=data.client_id, contract_number="PENDING", occupancy_type=data.occupancy_type, start_at=data.start_at, end_at=data.end_at, rate_snapshot=rate, deposit_snapshot=unit.deposit_amount, total_amount=total, billing_day=data.billing_day, created_by_name=_agent(current_user))
    db.add(item); db.flush(); item.contract_number = f"IMMO-{datetime.utcnow():%Y%m%d}-{item.id:05d}"
    if data.occupancy_type == "lease":
        months = 12 if data.end_at is None else max(1, ceil((data.end_at - data.start_at).days / 30.44))
        billing_day = data.billing_day or min(data.start_at.day, 28)
        for index in range(months):
            item.dues.append(PropertyPaymentDue(enterprise_id=enterprise_id, due_date=_add_month(data.start_at, index, billing_day), amount=rate))
        item.total_amount = round(rate * months, 2)
    unit.status = "reserved"
    db.commit(); db.refresh(item)
    return {"id": item.id, "contract_number": item.contract_number, "occupancy_type": item.occupancy_type, "status": item.status, "total_amount": item.total_amount, "due_count": len(item.dues)}


@router.get("/occupancies")
def list_occupancies(offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);enterprise_id=actor_enterprise_id(current_user)
    items=db.query(PropertyOccupancy).options(selectinload(PropertyOccupancy.client),selectinload(PropertyOccupancy.unit),selectinload(PropertyOccupancy.dues)).filter(PropertyOccupancy.enterprise_id==enterprise_id).order_by(PropertyOccupancy.created_at.desc()).offset(offset).limit(limit).all()
    return [{"id":x.id,"contract_number":x.contract_number,"client_name":x.client.nom,"unit_name":x.unit.name,"occupancy_type":x.occupancy_type,"status":x.status,"total_amount":x.total_amount,"paid_amount":x.paid_amount,"deposit_held":x.deposit_held,"dues":[{"id":d.id,"due_date":d.due_date,"amount":d.amount,"paid_amount":d.paid_amount,"status":d.status} for d in x.dues]} for x in items]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    units = dict(db.query(PropertyUnit.status, func.count(PropertyUnit.id)).filter(PropertyUnit.enterprise_id == enterprise_id).group_by(PropertyUnit.status).all())
    due_amount = db.query(func.coalesce(func.sum(PropertyPaymentDue.amount - PropertyPaymentDue.paid_amount), 0)).filter(PropertyPaymentDue.enterprise_id == enterprise_id, PropertyPaymentDue.status != "paid").scalar()
    overdue = db.query(func.count(PropertyPaymentDue.id)).filter(PropertyPaymentDue.enterprise_id == enterprise_id, PropertyPaymentDue.due_date < datetime.utcnow(), PropertyPaymentDue.status != "paid").scalar() or 0
    return {"properties": db.query(func.count(RentalProperty.id)).filter(RentalProperty.enterprise_id == enterprise_id, RentalProperty.is_active.is_(True)).scalar() or 0, "units": sum(units.values()), "available": units.get("available", 0), "occupied": units.get("occupied", 0), "reserved": units.get("reserved", 0), "outstanding_amount": float(due_amount or 0), "overdue_count": overdue}


@router.post("/occupancies/{occupancy_id}/payments", status_code=201)
def record_payment(occupancy_id: int, data: PropertyPaymentCreate, db: Session = Depends(get_db), current_user=Depends(All_required())):
    _ensure(current_user); enterprise_id=actor_enterprise_id(current_user)
    occupancy=db.query(PropertyOccupancy).filter(PropertyOccupancy.id==occupancy_id,PropertyOccupancy.enterprise_id==enterprise_id).with_for_update().first()
    if not occupancy: raise HTTPException(404,"Contrat introuvable")
    due=None
    if data.kind=="rent":
        if not data.due_id: raise HTTPException(400,"L'échéance est obligatoire pour un paiement de loyer")
        due=db.query(PropertyPaymentDue).filter(PropertyPaymentDue.id==data.due_id,PropertyPaymentDue.occupancy_id==occupancy.id,PropertyPaymentDue.enterprise_id==enterprise_id).with_for_update().first()
        if not due: raise HTTPException(404,"Échéance introuvable")
        remaining=round(due.amount-due.paid_amount,2)
        if data.amount>remaining+0.001: raise HTTPException(409,f"Le paiement dépasse le reste de l'échéance ({remaining:.2f})")
        due.paid_amount=round(due.paid_amount+data.amount,2); due.status="paid" if due.paid_amount>=due.amount else "partial"; occupancy.paid_amount=round(occupancy.paid_amount+data.amount,2)
    elif data.kind=="deposit":
        remaining=round(occupancy.deposit_snapshot-occupancy.deposit_held,2)
        if data.amount>remaining+0.001: raise HTTPException(409,"La caution dépasse le montant prévu")
        occupancy.deposit_held=round(occupancy.deposit_held+data.amount,2)
    else:
        if data.amount>occupancy.deposit_held+0.001: raise HTTPException(409,"Le remboursement dépasse la caution détenue")
        occupancy.deposit_held=round(occupancy.deposit_held-data.amount,2)
    payment=PropertyPayment(enterprise_id=enterprise_id,occupancy_id=occupancy.id,due_id=due.id if due else None,kind=data.kind,amount=data.amount,payment_method=data.payment_method,reference=data.reference,agent_name=_agent(current_user))
    db.add(payment);db.commit();db.refresh(payment)
    return {"id":payment.id,"amount":payment.amount,"kind":payment.kind,"due_status":due.status if due else None,"deposit_held":occupancy.deposit_held}


@router.get("/overdue-alerts")
def overdue_alerts(limit:int=Query(50,ge=1,le=200),db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);enterprise_id=actor_enterprise_id(current_user);now=datetime.utcnow()
    rows=db.query(PropertyPaymentDue).options(selectinload(PropertyPaymentDue.occupancy).selectinload(PropertyOccupancy.client),selectinload(PropertyPaymentDue.occupancy).selectinload(PropertyOccupancy.unit)).filter(PropertyPaymentDue.enterprise_id==enterprise_id,PropertyPaymentDue.due_date<now,PropertyPaymentDue.status!="paid").order_by(PropertyPaymentDue.due_date).limit(limit).all()
    return [{"due_id":x.id,"occupancy_id":x.occupancy_id,"contract_number":x.occupancy.contract_number,"client_name":x.occupancy.client.nom,"unit_name":x.occupancy.unit.name,"due_date":x.due_date,"remaining":x.amount-x.paid_amount,"days_late":(now-x.due_date).days} for x in rows]


@router.post("/occupancies/{occupancy_id}/inspections",status_code=201)
def create_inspection(occupancy_id:int,data:PropertyInspectionCreate,db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);enterprise_id=actor_enterprise_id(current_user)
    if not db.query(PropertyOccupancy.id).filter(PropertyOccupancy.id==occupancy_id,PropertyOccupancy.enterprise_id==enterprise_id).first(): raise HTTPException(404,"Contrat introuvable")
    item=PropertyInspection(enterprise_id=enterprise_id,occupancy_id=occupancy_id,inspection_type=data.inspection_type,notes=data.notes,condition_json=data.condition,photos_json=data.photos,signed_by_client=data.signed_by_client,agent_name=_agent(current_user));db.add(item);db.commit();db.refresh(item)
    return {"id":item.id,"inspection_type":item.inspection_type,"created_at":item.created_at}


@router.post("/maintenance",status_code=201)
def create_maintenance(data:PropertyMaintenanceCreate,db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);enterprise_id=actor_enterprise_id(current_user)
    if not db.query(RentalProperty.id).filter(RentalProperty.id==data.property_id,RentalProperty.enterprise_id==enterprise_id).first(): raise HTTPException(404,"Bien introuvable")
    if data.unit_id and not db.query(PropertyUnit.id).filter(PropertyUnit.id==data.unit_id,PropertyUnit.property_id==data.property_id,PropertyUnit.enterprise_id==enterprise_id).first(): raise HTTPException(404,"Unité introuvable")
    item=PropertyMaintenance(enterprise_id=enterprise_id,agent_name=_agent(current_user),**data.model_dump());db.add(item);db.commit();db.refresh(item);return {"id":item.id,"title":item.title,"status":item.status}


@router.patch("/maintenance/{maintenance_id}")
def update_maintenance(maintenance_id:int,data:PropertyMaintenanceUpdate,db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);item=db.query(PropertyMaintenance).filter(PropertyMaintenance.id==maintenance_id,PropertyMaintenance.enterprise_id==actor_enterprise_id(current_user)).first()
    if not item: raise HTTPException(404,"Intervention introuvable")
    item.status=data.status
    if data.actual_cost is not None:item.actual_cost=data.actual_cost
    if data.status=="completed":item.completed_at=datetime.utcnow()
    db.commit();return {"id":item.id,"status":item.status,"actual_cost":item.actual_cost}


@router.get("/occupancies/{occupancy_id}/document")
def occupancy_document(occupancy_id:int,document_type:str=Query("lease",pattern="^(lease|receipt|inspection)$"),due_id:int|None=None,db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);enterprise_id=actor_enterprise_id(current_user)
    item=db.query(PropertyOccupancy).options(selectinload(PropertyOccupancy.client),selectinload(PropertyOccupancy.unit).selectinload(PropertyUnit.property)).filter(PropertyOccupancy.id==occupancy_id,PropertyOccupancy.enterprise_id==enterprise_id).first()
    if not item:raise HTTPException(404,"Contrat introuvable")
    enterprise=db.query(Enterprise).filter(Enterprise.id==enterprise_id).first();buffer=BytesIO();doc=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm);styles=getSampleStyleSheet();primary=colors.HexColor(getattr(enterprise,"invoice_color",None) or "#5C6BC0")
    titles={"lease":"CONTRAT DE LOCATION","receipt":"QUITTANCE DE LOYER","inspection":"ÉTAT DES LIEUX"};story=[Paragraph(enterprise.name if enterprise else "Trade Care",styles["Title"]),Paragraph(titles[document_type],styles["Heading1"]),Spacer(1,6*mm)]
    rows=[["Référence",item.contract_number],["Locataire",item.client.nom],["Bien",item.unit.property.name],["Unité",item.unit.name],["Début",item.start_at.strftime("%d/%m/%Y")],["Fin",item.end_at.strftime("%d/%m/%Y") if item.end_at else "Durée indéterminée"],["Tarif",f"{item.rate_snapshot:,.0f} {getattr(enterprise,'currency','XOF')}"],["Caution",f"{item.deposit_snapshot:,.0f} {getattr(enterprise,'currency','XOF')}"],["Agent",item.created_by_name]]
    if document_type=="receipt":
        due=db.query(PropertyPaymentDue).filter(PropertyPaymentDue.id==due_id,PropertyPaymentDue.occupancy_id==item.id).first() if due_id else None
        if not due or due.status!="paid":raise HTTPException(409,"Une quittance exige une échéance entièrement payée")
        rows.extend([["Échéance",due.due_date.strftime("%d/%m/%Y")],["Montant acquitté",f"{due.paid_amount:,.0f} {getattr(enterprise,'currency','XOF')}"]])
    table=Table(rows,colWidths=[55*mm,105*mm]);table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),primary),("TEXTCOLOR",(0,0),(0,-1),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#D6DAE4")),("PADDING",(0,0),(-1,-1),8)]));story.extend([table,Spacer(1,18*mm),Paragraph("Signature du locataire                                      Signature de l'entreprise",styles["BodyText"])]);doc.build(story);buffer.seek(0)
    return StreamingResponse(buffer,media_type="application/pdf",headers={"Content-Disposition":f'inline; filename="{document_type}_{item.contract_number}.pdf"'})


@router.get("/reminder-settings")
def get_reminder_settings(db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user);return reminder_settings(db,actor_enterprise_id(current_user))


@router.put("/reminder-settings")
def update_reminder_settings(data:PropertyReminderSettings,db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user)
    if not current_user.is_main_user and str(getattr(current_user,"role","")).lower()!="admin":raise HTTPException(403,"Seuls les administrateurs peuvent configurer les relances")
    return save_reminder_settings(db,actor_enterprise_id(current_user),data.model_dump())


@router.post("/reminders/run")
async def run_reminders(db:Session=Depends(get_db),current_user=Depends(All_required())):
    _ensure(current_user)
    if not current_user.is_main_user and not getattr(current_user,"is_superuser",False):raise HTTPException(403,"Action réservée au compte principal")
    return await dispatch_property_reminders(db,actor_enterprise_id(current_user))
