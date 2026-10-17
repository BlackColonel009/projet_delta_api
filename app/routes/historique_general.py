# 📡 ROUTES POUR L'HISTORIQUE GÉNÉRAL
# Fichier : app/routes/historique.py
from app.utils.security import require_super_user
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.model_historique_general import Historique
from app.schemas.historique_general_schema import HistoriqueOut, HistoriqueCreate
from app.utils.security import get_current_user
from app.utils.permissions import All_required
from app.models.model_user import User, SubUser
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter

router = APIRouter(prefix="/historiques", tags=["Historique"])

# ➕ Ajouter une entrée historique
@router.post("/", response_model=HistoriqueOut)
def add_historique(
    data: HistoriqueCreate,
    db: Session = Depends(get_db),
    current_user = Depends(All_required())  # ✅ OK : FastAPI va exécuter la dépendance

):
    h = Historique(
        **data.dict(),
        user_id=actor_owner_id(current_user),
        enterprise_id=actor_enterprise_id(current_user),
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h

# Historique de l'entreprise, enrichi avec l'auteur de chaque action.
@router.get("/", response_model=List[dict])
def list_historiques(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    type_entite: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(All_required())  # ✅ OK : FastAPI va exécuter la dépendance

):
    query = db.query(Historique).options(
        joinedload(Historique.user),
        joinedload(Historique.sub_user)
    ).filter(enterprise_scope_filter(Historique, current_user))

    if start:
        query = query.filter(Historique.date_action >= start)
    if end:
        query = query.filter(Historique.date_action <= end)
    if type_entite:
        query = query.filter(Historique.type_entite == type_entite)

    historiques = (
        query.order_by(Historique.date_action.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    result = []
    for h in historiques:
        result.append({
            "id": h.id,
            "action": h.action,
            "type_entite": h.type_entite,
            "entite_id": h.entite_id,
            "details": h.details,
            "date_action": h.date_action,
            "done_by": (
                h.sub_user.username
                if h.sub_user
                else h.user.email if h.user else "Inconnu"
            ),
            "actor_type": "Employé" if h.sub_user else "Administrateur",
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
