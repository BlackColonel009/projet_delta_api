from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.model_historique_intervention import HistoriqueIntervention
from app.schemas.historique_intervention_schema import HistInterventionOut, HistInterventionCreate
from app.utils.security import get_current_user
from app.utils.permissions import technicien_required
from app.models.model_intervention import Intervention
from app.models.model_produit import Produit
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter

router = APIRouter(prefix="/historiques/interventions", tags=["Historique Interventions"])

# ➕ Créer une entrée
@router.post("/", response_model=HistInterventionOut)
def create_historique_intervention(
    data: HistInterventionCreate,
    db: Session = Depends(get_db),
    current_user= Depends(technicien_required())
):
    if not db.query(Intervention).filter(
        Intervention.id == data.intervention_id,
        enterprise_scope_filter(Intervention, current_user),
    ).first() or not db.query(Produit).filter(
        Produit.id == data.produit_id,
        enterprise_scope_filter(Produit, current_user),
    ).first():
        raise HTTPException(status_code=404, detail="Intervention ou produit introuvable")
    h = HistoriqueIntervention(
        **data.dict(),
        user_id=actor_owner_id(current_user),
        enterprise_id=actor_enterprise_id(current_user),
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h

# 📋 Lister avec filtres par date, produit, ou intervention
@router.get("/", response_model=List[HistInterventionOut])
def list_historiques_interventions(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    produit_id: Optional[int] = Query(None),
    intervention_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user= Depends(technicien_required())
):
    query = db.query(HistoriqueIntervention).filter(
        enterprise_scope_filter(HistoriqueIntervention, current_user)
    )
    
    if start:
        query = query.filter(HistoriqueIntervention.date_action >= start)
    if end:
        query = query.filter(HistoriqueIntervention.date_action <= end)
    if produit_id:
        query = query.filter(HistoriqueIntervention.produit_id == produit_id)
    if intervention_id:
        query = query.filter(HistoriqueIntervention.intervention_id == intervention_id)

    return query.order_by(HistoriqueIntervention.date_action.desc()).all()
