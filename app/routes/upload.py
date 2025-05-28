from fastapi import File, HTTPException, UploadFile, Depends, APIRouter
from sqlalchemy.orm import Session
from uuid import uuid4
from app.database import get_db
from app.models.model_user import User, SubUser
from app.utils.security import get_current_user, get_current_sub_user
from app.utils.logger import log_action
from app.services.supabase_service import upload_to_supabase, delete_from_supabase

router = APIRouter(prefix="/upload", tags=["Fichiers"])

# 📄 Upload avatar utilisateur principal
@router.post("/avatar-user")
def upload_avatar_for_user(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = f"{uuid4()}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="avatars", filename=filename)

    current_user.avatar_url = file_url
    db.commit()
    db.refresh(current_user)

    log_action(
        db=db,
        current_user=current_user,
        action="Upload avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal mis à jour"
    )

    return {"avatar_url": file_url, "message": "Avatar uploaded and linked successfully."}


# 📄 Upload avatar sub-user
@router.post("/avatar-sub")
def upload_avatar_for_subuser(
    file: UploadFile = File(...),
    current_sub: SubUser = Depends(get_current_sub_user),
    db: Session = Depends(get_db)
):
    filename = f"{uuid4()}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="avatars", filename=filename)

    current_sub.avatar_url = file_url
    db.commit()
    db.refresh(current_sub)

    log_action(
        db=db,
        current_user=current_sub,
        action="Upload avatar",
        type_entite="sub-user",
        entite_id=current_sub.id,
        details="Avatar sub-user mis à jour"
    )

    return {"avatar_url": file_url, "message": "Avatar uploaded and linked successfully."}


# 👤 Get avatar utilisateur principal
@router.get("/avatar-user")
def get_avatar_user(current_user: User = Depends(get_current_user)):
    return {"avatar_url": current_user.avatar_url}


# 👤 Get avatar sub-user
@router.get("/avatar-sub")
def get_avatar_subuser(current_sub: SubUser = Depends(get_current_sub_user)):
    return {"avatar_url": current_sub.avatar_url}


# 🧽 Delete avatar utilisateur principal
@router.delete("/delete/avatar")
def delete_avatar_file(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Aucun avatar défini.")

    delete_from_supabase(current_user.avatar_url)
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal supprimé"
    )

    return {"message": "Avatar supprimé avec succès."}


# ****************** LOGO ********************
@router.post("/logo")
def upload_logo_entreprise(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = f"logo_{current_user.id}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="logos", filename=filename)

    current_user.logo_entreprise = file_url
    db.commit()
    db.refresh(current_user)

    return {"logo_url": file_url}


@router.get("/logo")
def get_logo_entreprise(current_user: User = Depends(get_current_user)):
    if not current_user.logo_entreprise:
        raise HTTPException(status_code=404, detail="Aucun logo enregistré")
    return {"logo_url": current_user.logo_entreprise}


@router.delete("/delete/logo")
def delete_logo_entreprise(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):

    if not current_user.logo_entreprise:
        raise HTTPException(status_code=404, detail="Aucun logo défini")

    delete_from_supabase(current_user.logo_entreprise)
    current_user.logo_entreprise = None
    db.commit()
    db.refresh(current_user)

    return {"message": "Logo supprimé"}
