import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_tutoriel import Tutoriel
from app.schemas.tutoriel_schema import TutorielOut
from app.utils.save_file_locally import save_file_locally
from app.utils.security import require_super_user
  # à adapter selon ton projet

router = APIRouter(prefix="/public/tutoriels", tags=["TUTORIELS"])

@router.post("/", response_model=TutorielOut)
def create_tutoriel(
    titre: str = Form(...),
    description: str = Form(None),
    navigation: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_url = save_file_locally(image) if image else None

    tutoriel = Tutoriel(
        titre=titre,
        description=description,
        navigation=navigation,
        image_url=image_url
    )
    db.add(tutoriel)
    db.commit()
    db.refresh(tutoriel)
    return tutoriel

@router.put("/{id}", response_model=TutorielOut)
def update_tutoriel(
    id: int,
    titre: str = Form(...),
    description: str = Form(None),
    navigation: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    tutoriel = db.query(Tutoriel).filter(Tutoriel.id == id).first()

    if not tutoriel:
        raise HTTPException(status_code=404, detail="Tutoriel introuvable")

    tutoriel.titre = titre
    tutoriel.description = description
    tutoriel.navigation = navigation

    if image:
        tutoriel.image_url = save_file_locally(image)

    db.commit()
    db.refresh(tutoriel)
    return tutoriel

@router.get("/", response_model=list[TutorielOut])
def get_all_tutoriels(db: Session = Depends(get_db)):
    return db.query(Tutoriel).order_by(Tutoriel.created_at.desc()).all()

@router.delete("/{id}")
def delete_tutoriel(
    id: int,
    db: Session = Depends(get_db),
    # current_user = Depends(require_super_user)
):
    # if not current_user:
        # HTTPException(status_code= 401, detail= "Vous n'êtes pas un superAdmin")

    
    tutoriel = db.query(Tutoriel).filter(Tutoriel.id == id).first()
    if not tutoriel:
        raise HTTPException(status_code=404, detail="Tutoriel introuvable")

    # Supprimer l'image du disque si elle existe
    if tutoriel.image_url:
        path = tutoriel.image_url.replace("/static", "upload")
        if os.path.exists(path):
            os.remove(path)

    db.delete(tutoriel)
    db.commit()
    return {"message": "Tutoriel supprimé avec succès"}