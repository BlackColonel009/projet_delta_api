from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.security import get_current_user
from app.models.model_user import User
import shutil, os
from uuid import uuid4

router = APIRouter(prefix="/upload", tags=["Upload fichiers"])

# ✅ Upload avatar
def save_file_locally(file: UploadFile, folder: str) -> str:
    ext = file.filename.split('.')[-1]
    filename = f"{uuid4()}.{ext}"
    upload_dir = os.path.join("upload", folder)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return f"/static/{folder}/{filename}"

@router.post("/avatar-user")
def upload_avatar_user(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.avatar_url = save_file_locally(file, "avatars")
    db.commit()
    db.refresh(current_user)
    return {"avatar_url": current_user.avatar_url}

@router.get("/avatar-user")
def get_avatar_user(current_user: User = Depends(get_current_user)):
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Aucun avatar trouvé")
    return {"avatar_url": current_user.avatar_url}

@router.delete("/delete/avatar")
def delete_avatar_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Aucun avatar défini")

    filepath = current_user.avatar_url.replace("/static", "upload")
    if os.path.exists(filepath):
        os.remove(filepath)

    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    return {"message": "Avatar supprimé"}

# ✅ Upload logo entreprise
@router.post("/logo")
def upload_logo_entreprise(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.logo_url = save_file_locally(file, "logos")
    db.commit()
    db.refresh(current_user)
    return {"logo_url": current_user.logo_url}

@router.get("/logo")
def get_logo(current_user: User = Depends(get_current_user)):
    if not current_user.logo_url:
        raise HTTPException(status_code=404, detail="Aucun logo défini")
    return {"logo_url": current_user.logo_url}

@router.delete("/delete/logo")
def delete_logo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.logo_url:
        raise HTTPException(status_code=404, detail="Aucun logo défini")

    filepath = current_user.logo_url.replace("/static", "upload")
    if os.path.exists(filepath):
        os.remove(filepath)

    current_user.logo_url = None
    db.commit()
    db.refresh(current_user)
    return {"message": "Logo supprimé"}
