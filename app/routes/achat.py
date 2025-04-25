from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_achat import Achat
from app.schemas.achat_schema import AchatOut, AchatCreate

router = APIRouter(prefix="/achats", tags=["Achats"])

# ➕ Créer un achat
@router.post("/", response_model=AchatOut)
def create_achat(data: AchatCreate, db: Session = Depends(get_db)):
    achat = Achat(**data.dict())
    db.add(achat)

    # 🧮 Mise à jour automatique du stock produit
    from app.models.model_produit import Produit
    produit = db.query(Produit).filter(Produit.id == achat.produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit lié introuvable")
    produit.quantite += achat.quantite

    db.commit()
    db.refresh(achat)
    return achat


# 📋 Lister tous les achats
@router.get("/", response_model=List[AchatOut])
def list_achats(db: Session = Depends(get_db)):
    return db.query(Achat).all()

# 🔍 Voir un achat par ID
@router.get("/{achat_id}", response_model=AchatOut)
def get_achat(achat_id: int, db: Session = Depends(get_db)):
    achat = db.query(Achat).filter(Achat.id == achat_id).first()
    if not achat:
        raise HTTPException(status_code=404, detail="Achat non trouvé")
    return achat

# 🔄 Modifier un achat
@router.put("/{achat_id}", response_model=AchatOut)
def update_achat(achat_id: int, data: AchatCreate, db: Session = Depends(get_db)):
    achat = db.query(Achat).filter(Achat.id == achat_id).first()
    if not achat:
        raise HTTPException(status_code=404, detail="Achat non trouvé")
    for key, value in data.dict().items():
        setattr(achat, key, value)
    db.commit()
    db.refresh(achat)
    return achat

# ❌ Supprimer un achat
@router.delete("/{achat_id}")
def delete_achat(achat_id: int, db: Session = Depends(get_db)):
    achat = db.query(Achat).filter(Achat.id == achat_id).first()
    if not achat:
        raise HTTPException(status_code=404, detail="Achat non trouvé")
    db.delete(achat)
    db.commit()
    return {"message": "Achat supprimé avec succès"}
