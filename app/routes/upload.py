from fastapi import File, UploadFile, Depends
from app.utils.security import get_current_user
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_user import User, SubUser
import shutil
import os
from uuid import uuid4
from fastapi import APIRouter
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_sub_user, require_role, 
    require_super_user, require_any_role, require_main_user)

router = APIRouter(prefix="/upload", tags=["Fichiers"])

@router.post("/avatar-user", tags=["Fichiers"])
def upload_avatar_for_user(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    📤 Upload d'un avatar pour utilisateur principal + mise à jour automatique du champ avatar_url
    """
    from uuid import uuid4
    import os, shutil

    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    path = os.path.join("upload", "avatars", filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url = f"/static/avatars/{filename}"
    current_user.avatar_url = url
    db.commit()
    
    log_action(
        db=db,
        current_user=current_user,
        action="Upload avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal mis à jour"
    )


    return {"avatar_url": url, "message": "Avatar uploaded and linked successfully."}


@router.post("/avatar-sub", tags=["Fichiers"])
def upload_avatar_for_subuser(
    file: UploadFile = File(...),
    current_sub: SubUser = Depends(get_current_sub_user),
    db: Session = Depends(get_db)
):
    """
    📤 Upload d'un avatar pour sub-user + mise à jour automatique du champ avatar_url
    """
    from uuid import uuid4
    import os, shutil

    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    path = os.path.join("upload", "avatars", filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url = f"/static/avatars/{filename}"
    current_sub.avatar_url = url
    db.commit()

    log_action(
        db=db,
        current_user=current_sub,
        action="Upload avatar",
        type_entite="sub-user",
        entite_id=current_sub.id,
        details="Avatar sub-user mis à jour"
    )

    
    return {"avatar_url": url, "message": "Avatar uploaded and linked successfully."}

# 👤 Avatar de l'utilisateur principal
@router.get("/avatar-user", tags=["Fichiers"])
def get_avatar_user(
    current_user: User = Depends(get_current_user),
):
    return {"avatar_url": current_user.avatar_url}


# 👤 Avatar du sub-user connecté
@router.get("/avatar-sub", tags=["Fichiers"])
def get_avatar_subuser(
    current_sub: SubUser = Depends(get_current_sub_user),
):
    return {"avatar_url": current_sub.avatar_url}

@router.delete("/delete/avatar", tags=["Fichiers"])
def delete_avatar_file(current_user: User = Depends(get_current_user)):
    """
    🧽 Supprimer le fichier avatar actuel de l'utilisateur (si défini)
    """
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Aucun avatar défini.")

    path = current_user.avatar_url.replace("/static", "upload")
    if os.path.exists(path):
        os.remove(path)
    current_user.avatar_url = None
    db = next(get_db())
    db.commit()
    
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal supprimé"
    )

    
    return {"message": "Avatar supprimé avec succès."}
