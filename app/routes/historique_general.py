# 📡 ROUTES POUR L'HISTORIQUE GÉNÉRAL
# Fichier : app/routes/historique.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.model_historique_general import Historique
from pydantic import BaseModel
from app.schemas.historique_general_schema import HistoriqueOut, HistoriqueCreate

router = APIRouter(prefix="/historiques", tags=["Historique"])


# ➕ Ajouter une entrée historique
@router.post("/", response_model=HistoriqueOut)
def add_historique(data: HistoriqueCreate, db: Session = Depends(get_db)):
    h = Historique(**data.dict())
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
    db: Session = Depends(get_db)
):
    query = db.query(Historique)
    if start:
        query = query.filter(Historique.date_action >= start)
    if end:
        query = query.filter(Historique.date_action <= end)
    if type_entite:
        query = query.filter(Historique.type_entite == type_entite)
    return query.order_by(Historique.date_action.desc()).all()
