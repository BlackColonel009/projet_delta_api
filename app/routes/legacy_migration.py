from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.model_client import Client
from app.models.model_depot import Depot
from app.models.model_enterprise import Enterprise, EnterpriseGroup
from app.models.model_legacy_migration import LegacyClientMapping, LegacyMigrationBatch, LegacyMigrationItem
from app.models.model_laundry import LaundryItem, LaundryOrder, LaundryOrderEvent, LaundryService
from app.utils.security import require_main_user

router = APIRouter(prefix="/legacy-consignment-migration", tags=["Migration Consigne"])


class MigrationRequest(BaseModel):
    source_enterprise_id: int
    target_enterprise_id: int


STATUS_MAP = {"en_attente":"received","recu":"received","stocke":"processing","pret_retrait":"ready","retire":"delivered","paye":"delivered","annule":"cancelled","facture":"ready","facture_creee":"ready"}


def _scope(db, user, data):
    group=db.query(EnterpriseGroup).filter(EnterpriseGroup.owner_user_id==user.id).first()
    if not group:raise HTTPException(404,"Groupe d'entreprises introuvable")
    source=db.query(Enterprise).filter(Enterprise.id==data.source_enterprise_id,Enterprise.group_id==group.id).first()
    target=db.query(Enterprise).filter(Enterprise.id==data.target_enterprise_id,Enterprise.group_id==group.id,Enterprise.business_type=="laundry",Enterprise.status=="active").first()
    if not source:raise HTTPException(404,"Entreprise source introuvable")
    if not target:raise HTTPException(409,"La destination doit être une entreprise Pressing active du même groupe")
    if source.id==target.id:raise HTTPException(409,"La source et la destination doivent être différentes")
    return group,source,target


def _depots(db, source, owner_id):
    scope=Depot.enterprise_id==source.id
    if source.is_primary:scope=or_(scope,and_(Depot.enterprise_id.is_(None),Depot.user_id==owner_id))
    return db.query(Depot).options(selectinload(Depot.client),selectinload(Depot.service),selectinload(Depot.facture)).filter(scope).order_by(Depot.id).all()


@router.post("/preview")
def preview(data:MigrationRequest,db:Session=Depends(get_db),current_user=Depends(require_main_user)):
    _,source,target=_scope(db,current_user,data);rows=_depots(db,source,current_user.id)
    migrated_ids={x[0] for x in db.query(LegacyMigrationItem.source_depot_id).filter(LegacyMigrationItem.source_depot_id.in_([d.id for d in rows])).all()} if rows else set()
    compatible=[];excluded=[]
    for depot in rows:
        if depot.id in migrated_ids:excluded.append({"depot_id":depot.id,"reason":"Déjà copié lors d'une migration précédente"})
        elif not depot.client:excluded.append({"depot_id":depot.id,"reason":"Client introuvable"})
        elif not depot.service:excluded.append({"depot_id":depot.id,"reason":"Service de consigne introuvable"})
        else:compatible.append({"depot_id":depot.id,"client":depot.client.nom,"description":depot.description_bien,"service":depot.service.nom,"status":depot.statut,"amount":float(depot.prix_total or 0),"has_invoice":bool(depot.facture)})
    return {"source":{"id":source.id,"name":source.name},"target":{"id":target.id,"name":target.name},"total":len(rows),"compatible_count":len(compatible),"excluded_count":len(excluded),"compatible":compatible,"excluded":excluded,"safety":{"mode":"copy_only","source_deleted":False,"legacy_invoices_preserved":True}}


def _client(db, source, target, owner_id):
    mapping=db.query(LegacyClientMapping).filter(LegacyClientMapping.source_client_id==source.id,LegacyClientMapping.target_enterprise_id==target.id).first()
    if mapping:return db.query(Client).filter(Client.id==mapping.target_client_id).one()
    query=db.query(Client).filter(Client.enterprise_id==target.id)
    existing=None
    if source.email:existing=query.filter(func.lower(Client.email)==source.email.lower()).first()
    if not existing and source.telephone:existing=query.filter(Client.telephone==source.telephone).first()
    if not existing:
        existing=Client(nom=source.nom,telephone=source.telephone,email=source.email,entreprise=source.entreprise,adresse=source.adresse,user_id=owner_id,enterprise_id=target.id)
        db.add(existing);db.flush()
    db.add(LegacyClientMapping(source_client_id=source.id,target_client_id=existing.id,target_enterprise_id=target.id));db.flush();return existing


@router.post("/execute")
def execute(data:MigrationRequest,db:Session=Depends(get_db),current_user=Depends(require_main_user)):
    group,source,target=_scope(db,current_user,data);rows=_depots(db,source,current_user.id)
    batch=LegacyMigrationBatch(group_id=group.id,source_enterprise_id=source.id,target_enterprise_id=target.id,status="running",created_by_user_id=current_user.id,report_json={})
    db.add(batch);db.flush();copied=0;skipped=0
    for depot in rows:
        if db.query(LegacyMigrationItem.id).filter(LegacyMigrationItem.source_depot_id==depot.id).first():skipped+=1;continue
        if not depot.client or not depot.service:
            db.add(LegacyMigrationItem(batch_id=batch.id,source_depot_id=depot.id,status="excluded",reason="Client ou service introuvable",snapshot_json={"description":depot.description_bien}));skipped+=1;continue
        target_client=_client(db,depot.client,target,current_user.id)
        service=db.query(LaundryService).filter(LaundryService.enterprise_id==target.id,func.lower(LaundryService.name)==depot.service.nom.strip().lower()).first()
        quantity=max(1,int(depot.quantite or 1));total=float(depot.prix_total or depot.prix_personnalise or 0);unit_price=round(total/quantity,2)
        if not service:
            service=LaundryService(enterprise_id=target.id,user_id=current_user.id,name=depot.service.nom.strip(),description=depot.service.description,pricing_mode="per_item",unit_price=unit_price,turnaround_minutes=max(15,int(depot.duree_minutes or 1440)))
            db.add(service);db.flush()
        status=STATUS_MAP.get(depot.statut,"received");paid=total if depot.facture and depot.facture.statut in {"paye","payee","soldee"} else 0
        order=LaundryOrder(enterprise_id=target.id,user_id=current_user.id,client_id=target_client.id,order_number="PENDING",status=status,received_at=depot.date_depot or datetime.utcnow(),ready_at=depot.date_pret_retrait,delivered_at=depot.date_retrait,total=total,subtotal=total,paid_amount=paid,notes=f"Copie de la consigne historique #{depot.id}",created_by_name=current_user.username or current_user.email,created_by_role="main_user")
        db.add(order);db.flush();order.order_number=f"MIG-PRS-{order.id:06d}"
        order.items.append(LaundryItem(service_id=service.id,category=depot.description_bien[:80],description=depot.description_bien,quantity=quantity,unit_price_snapshot=unit_price,line_total=total,status=status,options_json={"legacy_depot_id":depot.id}))
        order.events.append(LaundryOrderEvent(from_status=None,to_status=status,note=f"Copié depuis la Consigne #{depot.id}; la source reste intacte",agent_name=current_user.username or current_user.email,agent_role="main_user"))
        db.add(LegacyMigrationItem(batch_id=batch.id,source_depot_id=depot.id,target_laundry_order_id=order.id,target_client_id=target_client.id,status="copied",snapshot_json={"legacy_status":depot.statut,"legacy_invoice_id":depot.facture.id if depot.facture else None,"amount":total}));copied+=1
    batch.status="completed";batch.completed_at=datetime.utcnow();batch.report_json={"copied":copied,"skipped":skipped,"source_preserved":True,"legacy_invoices_preserved":True};db.commit();db.refresh(batch)
    return {"batch_id":batch.id,"status":batch.status,**batch.report_json}


@router.get("/batches")
def batches(db:Session=Depends(get_db),current_user=Depends(require_main_user)):
    group=db.query(EnterpriseGroup).filter(EnterpriseGroup.owner_user_id==current_user.id).first()
    if not group:return []
    rows=db.query(LegacyMigrationBatch).filter(LegacyMigrationBatch.group_id==group.id).order_by(LegacyMigrationBatch.created_at.desc()).limit(30).all()
    return [{"id":x.id,"source_enterprise_id":x.source_enterprise_id,"target_enterprise_id":x.target_enterprise_id,"status":x.status,"report":x.report_json,"created_at":x.created_at} for x in rows]
