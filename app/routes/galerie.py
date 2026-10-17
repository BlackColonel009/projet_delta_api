from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_galerie import GaleriePhoto
from app.models.model_produit import Produit
from app.services.enterprise_service import actor_enterprise_id, enterprise_scope_filter
from typing import List
from app.schemas.galerie_schema import GalerieOut
import shutil, os
from uuid import uuid4
from datetime import datetime
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum


router = APIRouter(prefix="/galerie", tags=["Galerie Produit"])

@router.post("/", response_model=dict)
def ajouter_photo_galerie(
    produit_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    parent_user_id = (
        current_user.parent_user_id
        if not current_user.is_main_user
        else current_user.id
    )
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
        Produit.date_suppression.is_(None),
    ).first()
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
        enterprise_id=actor_enterprise_id(current_user),
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
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    image = db.query(GaleriePhoto).join(GaleriePhoto.produit).filter(
        GaleriePhoto.id == image_id,
        enterprise_scope_filter(GaleriePhoto, current_user),
    ).first()
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
def delete_image_galerie(
    image_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    image = db.query(GaleriePhoto).join(GaleriePhoto.produit).filter(
        GaleriePhoto.id == image_id,
        enterprise_scope_filter(GaleriePhoto, current_user),
    ).first()
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
def get_galerie_by_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([
        RoleEnum.admin,
        RoleEnum.gestionnaire_stock,
        RoleEnum.technicien,
        RoleEnum.caissier,
        RoleEnum.commercial,
    ])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    images = db.query(GaleriePhoto).join(GaleriePhoto.produit).filter(
        GaleriePhoto.produit_id == produit_id,
        enterprise_scope_filter(GaleriePhoto, current_user),
    ).order_by(GaleriePhoto.date_ajout.desc()).all()
    return images
