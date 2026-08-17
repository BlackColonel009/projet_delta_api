from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_facture_depot import FactureDepot
from app.schemas import facture_depot_schema as schemas
from datetime import datetime

router = APIRouter(prefix="/factures-depot", tags=["Factures Dépôt"])


@router.post("/", response_model=schemas.FactureDepotOut)
def create_facture_depot(payload: schemas.FactureDepotCreate, db: Session = Depends(get_db)):
    existing = db.query(FactureDepot).filter_by(depot_id=payload.depot_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une facture existe déjà pour ce dépôt.")

    facture = FactureDepot(
        **payload.dict(),
        date_facture=datetime.utcnow()
    )
    db.add(facture)
    db.commit()
    db.refresh(facture)
    return facture


@router.get("/{id}", response_model=schemas.FactureDepotOut)
def get_facture_depot(id: int, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).get(id)
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    return facture


@router.put("/{id}", response_model=schemas.FactureDepotOut)
def update_facture_depot(id: int, payload: schemas.FactureDepotUpdate, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).get(id)
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(facture, attr, value)

    db.commit()
    db.refresh(facture)
    return facture


@router.delete("/{id}")
def delete_facture_depot(id: int, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).get(id)
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    
    db.delete(facture)
    db.commit()
    return {"detail": "Facture supprimée"}


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from datetime import datetime
from starlette.responses import StreamingResponse
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph

from app.database import get_db
from app.models.model_facture_depot import FactureDepot
from app.models.model_depot import Depot


@router.get("/{facture_id}/preview")
def preview_facture_depot_pdf(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).options(
        joinedload(FactureDepot.depot).joinedload(Depot.client),
    ).filter(FactureDepot.id == facture_id).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture de dépôt non trouvée")

    depot = facture.depot
    if not depot:
        raise HTTPException(status_code=404, detail="Dépôt introuvable")

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    devise = facture.user.devise if hasattr(facture, "user") else "FCFA"

    # Logo entreprise si présent
    if hasattr(facture, "user") and getattr(facture.user, "logo_entreprise", None):
        try:
            logo = ImageReader(facture.user.logo_entreprise)
            pdf.drawImage(logo, 2 * cm, y - 1.5 * cm, width=4 * cm, preserveAspectRatio=True, mask='auto')
        except:
            pass  # Continue sans planter si logo invalide
    
    service_nom = facture.depot.service.nom if facture.depot and facture.depot.service else "Service inconnu"
    tarif_nom = facture.depot.tarif.nom_tarif if facture.depot and facture.depot.tarif else "Tarif inconnu"
   


    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(8 * cm, y, f"Facture retrait: {service_nom} #{facture.id}")
    y -= 1.5 * cm

    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Date : {facture.created_at.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if depot.client:
        pdf.drawString(2 * cm, y, f"Client : {depot.client.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Désignation")
    pdf.drawCentredString(10.25 * cm, y, "Qté")
    pdf.drawRightString(15.1 * cm, y, "PU")
    pdf.drawRightString(18.8 * cm, y, "Total")

    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleN.fontName = "Helvetica"
    styleN.fontSize = 9
    styleN.leading = 11

    y, total = draw_tarif_items(pdf, depot, y, devise, styleN)


    # y déjà décrémenté dans draw_tarif_items
    y -= 0.5 * cm  # petit espace avant le total


    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{total:.2f} {devise}")

    y -= 1 * cm
    # if facture.montant_ttc >= total:
    #     status_label = "PAYÉ"
    # else:
    #     status_label = "NON PAYÉ"

    # pdf.saveState()
    # pdf.setFont("Helvetica-Bold", 36)
    # pdf.setFillColorRGB(0.6, 0.1, 0.1)
    # pdf.translate(13 * cm, 5 * cm)
    # pdf.rotate(25)
    # pdf.drawString(0, 0, status_label)
    # pdf.restoreState()

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    pdf.drawCentredString(10.5 * cm, 1.5 * cm, "Merci pour votre confiance.")

    pdf.showPage()
    pdf.save()
    pdf_buffer.seek(0)

    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=facture_depot_{facture.id}.pdf"
    })

#facture_depot non payé au dépot souche.
@router.get("/{facture_id}/depot-preview")
def preview_facture_depot_pdf(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).options(
        joinedload(FactureDepot.depot).joinedload(Depot.client),
    ).filter(FactureDepot.id == facture_id).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture de dépôt non trouvée")

    depot = facture.depot
    if not depot:
        raise HTTPException(status_code=404, detail="Dépôt introuvable")

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    devise = facture.user.devise if hasattr(facture, "user") else "FCFA"

    # Logo entreprise si présent
    if hasattr(facture, "user") and getattr(facture.user, "logo_entreprise", None):
        try:
            logo = ImageReader(facture.user.logo_entreprise)
            pdf.drawImage(logo, 2 * cm, y - 1.5 * cm, width=4 * cm, preserveAspectRatio=True, mask='auto')
        except:
            pass  # Continue sans planter si logo invalide
    
    service_nom = facture.depot.service.nom if facture.depot and facture.depot.service else "Service inconnu"
    tarif_nom = facture.depot.tarif.nom_tarif if facture.depot and facture.depot.tarif else "Tarif inconnu"
   


    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(8 * cm, y, f"Preuve de dépôt: {service_nom} #{facture.id}")
    y -= 1.5 * cm

    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Date : {facture.created_at.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if depot.client:
        pdf.drawString(2 * cm, y, f"Client : {depot.client.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Désignation")
    pdf.drawCentredString(10.25 * cm, y, "Qté")
    pdf.drawRightString(15.1 * cm, y, "PU")
    pdf.drawRightString(18.8 * cm, y, "Total")

    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleN.fontName = "Helvetica"
    styleN.fontSize = 9
    styleN.leading = 11

    y, total = draw_tarif_items(pdf, depot, y, devise, styleN)


    # y déjà décrémenté dans draw_tarif_items
    y -= 0.5 * cm  # petit espace avant le total


    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{total:.2f} {devise}")


    y -= 1 * cm

    status_label = "NON PAYÉ"

    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 36)
    pdf.setFillColorRGB(0.6, 0.1, 0.1)
    pdf.translate(13 * cm, 5 * cm)
    pdf.rotate(25)
    pdf.drawString(0, 0, status_label)
    pdf.restoreState()

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    pdf.drawCentredString(10.5 * cm, 1.5 * cm, "Merci pour votre confiance.")

    pdf.showPage()
    pdf.save()
    pdf_buffer.seek(0)

    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=facture_depot_{facture.id}.pdf"
    })

def draw_tarif_items(pdf, depot, y, devise, styleN):
    total_general = 0.0
    for item in depot.tarif_items:
        nom_tarif = item.tarif.nom_tarif
        quantite = item.quantite
        pu = item.prix_personnalise or (
            item.tarif.tarif_unitaire or 0.0
        )  # fallback
        total = pu * quantite
        total_general += total
        description = item.description or ""

        para = Paragraph(f"<b>{nom_tarif} : {description}</b>", styleN)
        w, h = para.wrapOn(pdf, 7.2 * cm, y)
        para.drawOn(pdf, 2.3 * cm, y - h)

        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(10.25 * cm, y, str(quantite))
        pdf.drawRightString(15.1 * cm, y, f"{pu:.2f} {devise}")
        pdf.drawRightString(18.8 * cm, y, f"{total:.2f} {devise}")

        y -= h + 0.8 * cm
    return y, total_general
