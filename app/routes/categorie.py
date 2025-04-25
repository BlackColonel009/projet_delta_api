
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_categorie import Categorie
from app.schemas.categorie_schema import CategorieOut, CategorieCreate

router = APIRouter(prefix="/categories", tags=["Catégories"])

# ➕ Créer une catégorie
@router.post("/", response_model=CategorieOut)
def create_categorie(data: CategorieCreate, db: Session = Depends(get_db)):
    if db.query(Categorie).filter(Categorie.nom == data.nom).first():
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    categorie = Categorie(**data.dict())
    db.add(categorie)
    db.commit()
    db.refresh(categorie)
    return categorie

# 📋 Lister toutes les catégories
@router.get("/", response_model=List[CategorieOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Categorie).all()

# 🔍 Obtenir une catégorie par ID
@router.get("/{categorie_id}", response_model=CategorieOut)
def get_categorie(categorie_id: int, db: Session = Depends(get_db)):
    categorie = db.query(Categorie).filter(Categorie.id == categorie_id).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    return categorie

# 🔄 Modifier une catégorie
@router.put("/{categorie_id}", response_model=CategorieOut)
def update_categorie(categorie_id: int, data: CategorieCreate, db: Session = Depends(get_db)):
    categorie = db.query(Categorie).filter(Categorie.id == categorie_id).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    for key, value in data.dict().items():
        setattr(categorie, key, value)
    db.commit()
    db.refresh(categorie)
    return categorie

# ❌ Supprimer une catégorie
@router.delete("/{categorie_id}")
def delete_categorie(categorie_id: int, db: Session = Depends(get_db)):
    categorie = db.query(Categorie).filter(Categorie.id == categorie_id).first()
    if not categorie:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    db.delete(categorie)
    db.commit()
    return {"message": "Catégorie supprimée avec succès"}