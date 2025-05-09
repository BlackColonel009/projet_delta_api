from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter(tags=["Factures publiques"])

@router.get("/file/{filename}", include_in_schema=True)
def get_facture_pdf(filename: str):
    filepath = os.path.join("file", filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="application/pdf", filename=filename)
    raise HTTPException(status_code=404, detail="Fichier non trouvé")
