
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_fournisseur import Fournisseur
from app.schemas.fournisseur_schema import FournisseurCreate, FournisseurOut 

router = APIRouter(prefix="/fournisseurs", tags=["Fournisseurs"])


# ➕ Créer un fournisseur
@router.post("/", response_model=FournisseurOut)
def create_fournisseur(data: FournisseurCreate, db: Session = Depends(get_db)):
    fournisseur = Fournisseur(**data.dict())
    db.add(fournisseur)
    db.commit()
    db.refresh(fournisseur)
    return fournisseur

# 📋 Lister tous les fournisseurs
@router.get("/", response_model=List[FournisseurOut])
def list_fournisseurs(db: Session = Depends(get_db)):
    return db.query(Fournisseur).all()

# 🔍 Voir un fournisseur par ID
@router.get("/{fournisseur_id}", response_model=FournisseurOut)
def get_fournisseur(fournisseur_id: int, db: Session = Depends(get_db)):
    fournisseur = db.query(Fournisseur).filter(Fournisseur.id == fournisseur_id).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    return fournisseur

# 🔄 Modifier un fournisseur
@router.put("/{fournisseur_id}", response_model=FournisseurOut)
def update_fournisseur(fournisseur_id: int, data: FournisseurCreate, db: Session = Depends(get_db)):
    fournisseur = db.query(Fournisseur).filter(Fournisseur.id == fournisseur_id).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    for key, value in data.dict().items():
        setattr(fournisseur, key, value)
    db.commit()
    db.refresh(fournisseur)
    return fournisseur

# ❌ Supprimer un fournisseur
@router.delete("/{fournisseur_id}")
def delete_fournisseur(fournisseur_id: int, db: Session = Depends(get_db)):
    fournisseur = db.query(Fournisseur).filter(Fournisseur.id == fournisseur_id).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")
    db.delete(fournisseur)
    db.commit()
    return {"message": "Fournisseur supprimé avec succès"}
