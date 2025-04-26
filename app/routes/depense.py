from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_depense import Depense
from app.schemas.depense_schema import DepenseCreate, DepenseOut

router = APIRouter(prefix="/depenses", tags=["Dépenses"])

# ➕ Ajouter une dépense
@router.post("/", response_model=DepenseOut)
def create_depense(data: DepenseCreate, db: Session = Depends(get_db)):
    depense = Depense(**data.dict())
    db.add(depense)
    db.commit()
    db.refresh(depense)
    return depense

# 📋 Lister toutes les dépenses
@router.get("/", response_model=List[DepenseOut])
def list_depenses(db: Session = Depends(get_db)):
    return db.query(Depense).order_by(Depense.date_depense.desc()).all()

#filtrer par catégorie
@router.get("/categorie/{categorie}", response_model=List[DepenseOut])
def list_depenses_par_categorie(categorie: str, db: Session = Depends(get_db)):
    depenses = db.query(Depense).filter(Depense.categorie == categorie).order_by(Depense.date_depense.desc()).all()
    return depenses


# ❌ Supprimer une dépense
@router.delete("/{depense_id}")
def delete_depense(depense_id: int, db: Session = Depends(get_db)):
    depense = db.query(Depense).filter(Depense.id == depense_id).first()
    if not depense:
        raise HTTPException(status_code=404, detail="Dépense non trouvée")
    db.delete(depense)
    db.commit()
    return {"message": "Dépense supprimée avec succès"}
