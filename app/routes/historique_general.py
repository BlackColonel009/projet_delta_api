# 📡 ROUTES POUR L'HISTORIQUE GÉNÉRAL
# Fichier : app/routes/historique.py
from app.utils.security import require_super_user
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.model_historique_general import Historique
from app.schemas.historique_general_schema import HistoriqueOut, HistoriqueCreate
from app.utils.security import get_current_user
from app.utils.permissions import All_required
from app.models.model_user import User, SubUser

router = APIRouter(prefix="/historiques", tags=["Historique"])

# ➕ Ajouter une entrée historique
@router.post("/", response_model=HistoriqueOut)
def add_historique(
    data: HistoriqueCreate,
    db: Session = Depends(get_db),
    current_user = Depends(All_required())  # ✅ OK : FastAPI va exécuter la dépendance

):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    h = Historique(**data.dict(), user_id=parent_user_id)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h

# 📋 Lister avec filtres par date/heure
@router.get("/", response_model=List[HistoriqueOut])
def list_historiques(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    type_entite: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(All_required())

):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(Historique).filter(Historique.user_id == parent_user_id)
    
    if start:
        query = query.filter(Historique.date_action >= start)
    if end:
        query = query.filter(Historique.date_action <= end)
    if type_entite:
        query = query.filter(Historique.type_entite == type_entite)

    return query.order_by(Historique.date_action.desc()).all()


#Get historique all data
@router.get("/", response_model=List[dict])
def list_historiques(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    type_entite: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(All_required())  # ✅ OK : FastAPI va exécuter la dépendance

):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    query = db.query(Historique).options(
        joinedload(Historique.user),
        joinedload(Historique.sub_user)
    ).filter(Historique.user_id == parent_user_id)

    if start:
        query = query.filter(Historique.date_action >= start)
    if end:
        query = query.filter(Historique.date_action <= end)
    if type_entite:
        query = query.filter(Historique.type_entite == type_entite)

    historiques = query.order_by(Historique.date_action.desc()).all()

    result = []
    for h in historiques:
        result.append({
            "id": h.id,
            "action": h.action,
            "type_entite": h.type_entite,
            "entite_id": h.entite_id,
            "details": h.details,
            "date_action": h.date_action,
            "done_by": h.sub_user.username if h.sub_user else h.user.email
        })

    return result

# 📡 ROUTE ADMIN POUR CONSULTER TOUS LES LOGS
@router.get("/admin/historiques", response_model=List[HistoriqueOut], tags=["Admin"])
def list_all_logs_superadmin(
    db: Session = Depends(get_db),
    current_super: User = Depends(require_super_user),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    type_entite: Optional[str] = Query(None),
):
    query = db.query(Historique)

    if start:
        query = query.filter(Historique.date_action >= start)
    if end:
        query = query.filter(Historique.date_action <= end)
    if type_entite:
        query = query.filter(Historique.type_entite == type_entite)

    return query.order_by(Historique.date_action.desc()).all()