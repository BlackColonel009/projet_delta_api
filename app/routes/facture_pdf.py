import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi_mail import FastMail, MessageSchema, MessageType
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from app.database import get_db
from app.models.model_facture import Facture
from app.utils.security import get_current_user
from app.config import conf

router = APIRouter(prefix="/factures", tags=["Email"])

# 📧 Envoyer une facture par mail au client
@router.post("/{facture_id}/send")
async def send_facture_to_client(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 🔐 Sécurité : s'assurer que la facture appartient au bon utilisateur
    facture = db.query(Facture).filter(
        Facture.id == facture_id,
        Facture.user_id == current_user.id
    ).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    if not facture.client or not facture.client.email:
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")

    # 🔧 Créer le dossier si nécessaire
    os.makedirs("factures", exist_ok=True)

    # 📄 Générer le fichier PDF
    pdf_path = f"factures/facture_{facture.id}.pdf"
    pdf = canvas.Canvas(pdf_path, pagesize=A4)
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
    pdf.drawString(2 * cm, y, "Description")
    pdf.drawString(9 * cm, y, "Qté")
    pdf.drawString(11 * cm, y, "PU")
    pdf.drawString(14 * cm, y, "Total")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 10)
    for ligne in facture.lignes:
        pdf.drawString(2 * cm, y, ligne.description)
        pdf.drawRightString(10 * cm, y, str(ligne.quantite))
        pdf.drawRightString(13 * cm, y, f"{ligne.prix_unitaire:.2f} FCFA")
        pdf.drawRightString(18 * cm, y, f"{ligne.total_ligne:.2f} FCFA")
        y -= 0.6 * cm
        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total HT :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} FCFA")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, f"TVA ({facture.tva:.0f}%) :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc - facture.total_ht:.2f} FCFA")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} FCFA")

    pdf.showPage()
    pdf.save()

    # 📧 Préparer l'e-mail
    message = MessageSchema(
        subject=f"Votre facture #{facture.id}",
        recipients=[facture.client.email],
        body=f"Bonjour, veuillez trouver en pièce jointe la facture #{facture.id}.",
        subtype=MessageType.plain,
        attachments=[pdf_path]
    )

    fm = FastMail(conf)
    await fm.send_message(message)

    return {"message": f"Facture #{facture.id} envoyée à {facture.client.email}"}
