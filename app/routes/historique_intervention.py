from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.model_historique_intervention import HistoriqueIntervention
from app.schemas.historique_intervention_schema import HistInterventionOut, HistInterventionCreate
from app.utils.security import get_current_user

router = APIRouter(prefix="/historiques/interventions", tags=["Historique Interventions"])

# ➕ Créer une entrée
@router.post("/", response_model=HistInterventionOut)
def create_historique_intervention(
    data: HistInterventionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    h = HistoriqueIntervention(**data.dict(), user_id=current_user.id)
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
    current_user=Depends(get_current_user)
):
    query = db.query(HistoriqueIntervention).filter(HistoriqueIntervention.user_id == current_user.id)
    
    if start:
        query = query.filter(HistoriqueIntervention.date_action >= start)
    if end:
        query = query.filter(HistoriqueIntervention.date_action <= end)
    if produit_id:
        query = query.filter(HistoriqueIntervention.produit_id == produit_id)
    if intervention_id:
        query = query.filter(HistoriqueIntervention.intervention_id == intervention_id)

    return query.order_by(HistoriqueIntervention.date_action.desc()).all()
