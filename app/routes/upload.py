from fastapi import File, UploadFile
import shutil
import os
from uuid import uuid4

@router.post("/upload/avatar", tags=["Fichiers"])
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

    return {"avatar_url": url, "message": "Avatar uploaded and linked successfully."}


@router.post("/upload/avatar-sub", tags=["Fichiers"])
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

    return {"avatar_url": url, "message": "Avatar uploaded and linked successfully."}

@router.post("/upload/avatar-sub", tags=["Fichiers"])
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

    return {"avatar_url": url, "message": "Avatar uploaded and linked successfully."}
