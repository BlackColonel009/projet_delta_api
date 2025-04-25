from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_vente import Vente
from app.schemas.vente_schema import VenteOut, VenteCreate

router = APIRouter(prefix="/ventes", tags=["Ventes"])

# ➕ Créer une vente + mise à jour du stock
@router.post("/", response_model=VenteOut)
def create_vente(data: VenteCreate, db: Session = Depends(get_db)):
    from app.models.model_produit import Produit

    produit = db.query(Produit).filter(Produit.id == data.produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    if produit.quantite < data.quantite:
        raise HTTPException(status_code=400, detail="Stock insuffisant pour cette vente")

    # Réduction du stock
    produit.quantite -= data.quantite

    # Calcul du prix total
    prix_total = produit.prix_vente * data.quantite

    vente = Vente(**data.dict(), prix_total=prix_total)
    db.add(vente)
    db.commit()
    db.refresh(vente)
    return vente

# 📋 Lister toutes les ventes
@router.get("/", response_model=List[VenteOut])
def list_ventes(db: Session = Depends(get_db)):
    return db.query(Vente).all()

# 🔍 Voir une vente par ID
@router.get("/{vente_id}", response_model=VenteOut)
def get_vente(vente_id: int, db: Session = Depends(get_db)):
    vente = db.query(Vente).filter(Vente.id == vente_id).first()
    if not vente:
        raise HTTPException(status_code=404, detail="Vente non trouvée")
    return vente

# ❌ Supprimer une vente
@router.delete("/{vente_id}")
def delete_vente(vente_id: int, db: Session = Depends(get_db)):
    vente = db.query(Vente).filter(Vente.id == vente_id).first()
    if not vente:
        raise HTTPException(status_code=404, detail="Vente non trouvée")
    db.delete(vente)
    db.commit()
    return {"message": "Vente supprimée avec succès"}
