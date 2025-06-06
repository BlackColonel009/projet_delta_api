# ✅ Routes corrigées : aperçu PDF + envoi email avec nom produit, quantité, PU, total ligne

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import StreamingResponse
from fastapi_mail import FastMail, MessageSchema, MessageType
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from io import BytesIO
from app.database import get_db
from app.models.model_facture import Facture
from app.utils.permissions import All_required, check_role
from app.schemas.user_schema import RoleEnum
from app.config import conf
from app.models.model_facture import LigneFacture 

router = APIRouter(prefix="/factures", tags=["Facturation"])

@router.get("/{facture_id}/preview")
def preview_facture_pdf(
    facture_id: int,
    db: Session = Depends(get_db),
    
):
    devise = ""
    facture = db.query(Facture).options(
        joinedload(Facture.lignes).joinedload(LigneFacture.produit),
        joinedload(Facture.client),
        joinedload(Facture.fournisseur),
        joinedload(Facture.paiements)
    ).filter(Facture.id == facture_id).first()

    joinedload(Facture.lignes).joinedload(LigneFacture.produit) 

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    total_paye = sum(p.montant for p in facture.paiements) if facture.paiements else 0.0

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"Facture #{facture.id} - {facture.type.value.upper()}")
    y -= 1.2 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Date : {facture.date_creation.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if facture.client:
        pdf.drawString(2 * cm, y, f"Client : {facture.client.nom}")
        y -= 0.6 * cm
    if facture.fournisseur:
        pdf.drawString(2 * cm, y, f"Fournisseur : {facture.fournisseur.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Produit")
    pdf.drawString(9 * cm, y, "Qté")
    pdf.drawString(11 * cm, y, "PU")
    pdf.drawString(14 * cm, y, "Total")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 10)
    for ligne in facture.lignes:
        nom_produit = ligne.produit.nom if ligne.produit else ligne.description
        pdf.drawString(2 * cm, y, nom_produit)
        pdf.drawRightString(10 * cm, y, str(ligne.quantite))
        pdf.drawRightString(13 * cm, y, f"{ligne.prix_unitaire:.2f} {devise}")
        pdf.drawRightString(18 * cm, y, f"{ligne.total_ligne:.2f} {devise}")
        y -= 0.6 * cm
        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total HT :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, f"TVA ({facture.tva:.0f}%) :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc - facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} {devise}")

    if total_paye >= facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, "PAYÉ")
        pdf.restoreState()
        
    if total_paye < facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, "NON PAYÉ")
        pdf.restoreState()
    
    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=facture_{facture.id}.pdf"
    })


@router.post("/{facture_id}/email-client")
async def send_facture_to_client_memory(
    facture_id: int,
    db: Session = Depends(get_db),
    # current_user=Depends(All_required())
):
    devise =  ""
    facture = db.query(Facture).options(
        joinedload(Facture.lignes).joinedload(LigneFacture.produit),
        joinedload(Facture.client),
        joinedload(Facture.fournisseur),
        joinedload(Facture.paiements)
    ).filter(Facture.id == facture_id).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    if not facture.client or not facture.client.email:
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")

    total_paye = sum(p.montant for p in facture.paiements) if facture.paiements else 0.0

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"Facture #{facture.id} - {facture.type.value.upper()}")
    y -= 1.2 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Date : {facture.date_creation.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if facture.client:
        pdf.drawString(2 * cm, y, f"Client : {facture.client.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Produit")
    pdf.drawString(9 * cm, y, "Qté")
    pdf.drawString(11 * cm, y, "PU")
    pdf.drawString(14 * cm, y, "Total")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 10)
    for ligne in facture.lignes:
        nom_produit = ligne.produit.nom if ligne.produit else ligne.description
        pdf.drawString(2 * cm, y, nom_produit)
        pdf.drawRightString(10 * cm, y, str(ligne.quantite))
        pdf.drawRightString(13 * cm, y, f"{ligne.prix_unitaire:.2f} {devise}")
        pdf.drawRightString(18 * cm, y, f"{ligne.total_ligne:.2f} {devise}")
        y -= 0.6 * cm
        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total HT :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, f"TVA ({facture.tva:.0f}%) :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc - facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} {devise}")

    if total_paye >= facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, "PAYÉ")
        pdf.restoreState()

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    # 1. Sauvegarder temporairement
    pdf_path = f"temp_facture_{facture.id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(buffer.getvalue())

    # 2. Envoyer par email
    message = MessageSchema(
        subject=f"Votre facture #{facture.id}",
        recipients=[facture.client.email],
        body=f"Bonjour, veuillez trouver en pièce jointe votre facture #{facture.id}.",
        subtype=MessageType.plain,
        attachments=[pdf_path]  # ✅ Chemin attendu par FastAPI-Mail
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    # 3. Supprimer le fichier temporaire après envoi
    import os
    os.remove(pdf_path)


    return {"message": f"Facture #{facture.id} envoyée à {facture.client.email}"}
