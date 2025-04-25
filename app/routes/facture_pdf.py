# 📄 ROUTE POUR GÉNÉRER UN PDF DE FACTURE AVEC WEASYPRINT
# Fichier : app/routes/facture_pdf.py

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_facture import Facture
from app.models.model_facture import LigneFacture
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os

router = APIRouter(prefix="/factures", tags=["PDF"])

TEMPLATE_DIR = os.path.join("app", "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

@router.get("/{facture_id}/pdf")
def generate_facture_pdf(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(Facture).filter(Facture.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    template = env.get_template("facture_template.html")
    rendered_html = template.render(facture=facture)

    pdf = HTML(string=rendered_html).write_pdf()

    return Response(content=pdf, media_type="application/pdf")
