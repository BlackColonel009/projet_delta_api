import os
import uuid
from fastapi import HTTPException, UploadFile


def save_file_locally(file: UploadFile, folder: str = "tutoriels") -> str:
    extension = file.filename.split(".")[-1]
    if extension.lower() not in ["jpg", "jpeg", "png", "gif"]:
        raise HTTPException(status_code=400, detail="Extension d'image non autorisée")

    filename = f"{uuid.uuid4()}.{extension}"
    save_dir = os.path.join("upload", folder)
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    return f"/static/{folder}/{filename}"