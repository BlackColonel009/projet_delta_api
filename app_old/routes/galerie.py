from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_galerie import GaleriePhoto
from app.models.model_produit import Produit
from typing import List
from app.schemas.galerie_schema import GalerieOut
import shutil, os
from uuid import uuid4
from datetime import datetime


router = APIRouter(prefix="/galerie", tags=["Galerie Produit"])

@router.post("/", response_model=dict)
def ajouter_photo_galerie(
    produit_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    path = os.path.join("upload", "galerie", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    g = GaleriePhoto(
        produit_id=produit_id,
        image_url=f"/static/galerie/{filename}",
        date_ajout=datetime.utcnow()
    )
    db.add(g)
    db.commit()
    db.refresh(g)

    return {"message": "Image ajoutée à la galerie", "image_url": g.image_url}


@router.put("/{image_id}", response_model=dict)
def update_image_galerie(
    image_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    image = db.query(GaleriePhoto).filter(GaleriePhoto.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image non trouvée")

    # Supprimer ancienne image si présente
    if image.image_url:
        old_path = image.image_url.replace("/static", "upload")
        if os.path.exists(old_path):
            os.remove(old_path)

    # Enregistrer la nouvelle image
    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    path = os.path.join("upload", "galerie", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image.image_url = f"/static/galerie/{filename}"
    db.commit()
    db.refresh(image)

    return {"message": "Image mise à jour avec succès", "image_url": image.image_url}

@router.delete("/{image_id}", response_model=dict)
def delete_image_galerie(image_id: int, db: Session = Depends(get_db)):
    image = db.query(GaleriePhoto).filter(GaleriePhoto.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image non trouvée")

    # Supprimer le fichier de stockage si présent
    if image.image_url:
        path = image.image_url.replace("/static", "upload")
        if os.path.exists(path):
            os.remove(path)

    db.delete(image)
    db.commit()

    return {"message": "Image supprimée avec succès"}



@router.get("/{produit_id}", response_model=List[GalerieOut])
def get_galerie_by_produit(produit_id: int, db: Session = Depends(get_db)):
    images = db.query(GaleriePhoto).filter(GaleriePhoto.produit_id == produit_id).order_by(GaleriePhoto.date_ajout.desc()).all()
    return images