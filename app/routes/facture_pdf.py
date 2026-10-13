# ✅ Routes corrigées : aperçu PDF + envoi email avec nom produit, quantité, PU, total ligne

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import FileResponse, StreamingResponse
from fastapi_mail import FastMail, MessageSchema, MessageType
from starlette.background import BackgroundTask
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from io import BytesIO
from app.database import get_db
from app.models.model_facture import Facture
from app.models.model_unite_produit import UniteProduit
from app.utils.permissions import All_required, check_role
from app.schemas.user_schema import RoleEnum
from app.config import conf
from app.models.model_facture import LigneFacture 
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from typing import Literal
import os
import tempfile

from app.services.generate_facture_from_commande import generate_facture_pdf
from app.utils.subscription_guard import enforce_feature_access
from app.utils.i18n import language_of, translated

router = APIRouter(prefix="/factures", tags=["Facturation"])

@router.get("/{facture_id}/preview")
def preview_facture_pdf(
    facture_id: int,
    invoice_format: Literal["simple", "professional"] = Query(
        "simple",
        alias="template",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    parent_user_id = (
        current_user.parent_user_id
        if not current_user.is_main_user
        else current_user.id
    )
    facture = db.query(Facture).options(
        joinedload(Facture.lignes).joinedload(LigneFacture.produit),
        joinedload(Facture.client),
        joinedload(Facture.fournisseur),
        joinedload(Facture.paiements)
    ).filter(
        Facture.id == facture_id,
        Facture.user_id == parent_user_id,
    ).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    if invoice_format == "professional":
        enforce_feature_access(db, current_user, "professional_invoice")
        pdf_path = generate_facture_pdf(facture, db)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"facture_professionnelle_{facture.id}.pdf",
            background=BackgroundTask(os.remove, pdf_path),
        )

    total_paye = sum(p.montant for p in facture.paiements) if facture.paiements else 0.0

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    devise = facture.user.devise if hasattr(facture, "user") else ""
    language = language_of(current_user)
    tr = lambda fr, en: translated(language, fr, en)

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"{tr('Facture', 'Invoice')} #{facture.id} - {facture.type.value.upper()}")
    y -= 1.2 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"{tr('Date :', 'Date:')} {facture.date_creation.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if facture.client:
        pdf.drawString(2 * cm, y, f"{tr('Client :', 'Customer:')} {facture.client.nom}")
        y -= 0.6 * cm
    if facture.fournisseur:
        pdf.drawString(2 * cm, y, f"{tr('Fournisseur :', 'Supplier:')} {facture.fournisseur.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, tr("Produit", "Product"))

    # Qté : centré entre 9.5 et 11
    pdf.drawCentredString(10.25 * cm, y, tr("Qté", "Qty"))

    # PU : aligné à droite à 15.1 cm
    pdf.drawRightString(15.1 * cm, y, "PU")

    # Total : aligné à droite à 18.8 cm
    pdf.drawRightString(18.8 * cm, y, "Total")

    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm


    pdf.setFont("Helvetica", 10)

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleN.fontName = "Helvetica"
    styleN.fontSize = 9
    styleN.leading = 11

    table_top_y = y + 0.5 * cm  # un peu plus haut que le début réel


    for ligne in facture.lignes:
        produit = ligne.produit
        nom_produit = produit.nom if produit else ligne.description

        # Caractéristiques produit
        caract_display = ""
        if produit and produit.caracteristiques:
            if isinstance(produit.caracteristiques, str):
                caract_display = produit.caracteristiques
            elif isinstance(produit.caracteristiques, dict):
                caract_display = ", ".join(f"{k}: {v}" for k, v in produit.caracteristiques.items())

        unites_concernees = []
        if produit and facture.commande_id:
            unites_concernees = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.commande_vente_id == facture.commande_id
            ).all()
        codes_display = ", ".join(u.tracabilite for u in unites_concernees if u.tracabilite)

        max_length = 150
        if len(codes_display) > max_length:
            codes_display = codes_display[:max_length] + "..."

        # Paragraphe avec retour à la ligne (7.2 cm max)
        text = f"<b>{nom_produit}</b><br/>"
        if caract_display:
            text += f"<i>{tr('Caractéristiques :', 'Details:')}</i> {caract_display}<br/>"
        if codes_display:
            text += f"<i>{tr('Codes :', 'Codes:')}</i> {codes_display}"

        para = Paragraph(text, styleN)
        max_para_width = 7.2 * cm
        w, h = para.wrapOn(pdf, max_para_width, y)
        para.drawOn(pdf, 2.3 * cm, y - h)

        # Qté (centré entre 9.5 et 11)
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(10.25 * cm, y, str(ligne.quantite))

        # PU (aligné à droite à 15.1)
        pdf.drawRightString(15.1 * cm, y, f"{ligne.prix_unitaire:.2f} {devise}")

        # Total (aligné à droite à 18.8)
        pdf.drawRightString(18.8 * cm, y, f"{ligne.total_ligne:.2f} {devise}")

        # Bordures verticales entre colonnes
        pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
        pdf.setLineWidth(0.3)
        pdf.line(9.5 * cm, y, 9.5 * cm, y - h)     # Produit | Qté
        pdf.line(11 * cm, y, 11 * cm, y - h)       # Qté | PU
        pdf.line(15.2 * cm, y, 15.2 * cm, y - h)   # PU | Total

        # Encadrement par ligne
        pdf.setStrokeColorRGB(0.85, 0.85, 0.85)
        pdf.rect(2 * cm, y - h, 17 * cm, h)

        # Ligne horizontale sous la ligne (par colonne, pour plus de clarté)
        line_y = y - h - 0.1 * cm
        pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
        pdf.setLineWidth(0.2)

        # Produit
        pdf.line(2 * cm, line_y, 9.5 * cm, line_y)
        # Qté
        pdf.line(9.5 * cm, line_y, 11 * cm, line_y)
        # PU
        pdf.line(11 * cm, line_y, 15.2 * cm, line_y)
        # Total
        pdf.line(15.2 * cm, line_y, 19 * cm, line_y)

        y -= h + 0.3 * cm

        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm


    pdf.setStrokeColorRGB(0.4, 0.4, 0.4)
    pdf.setLineWidth(0.6)
    table_height = table_top_y - y
    pdf.rect(2 * cm, y, 17 * cm, table_height)  # (x, y, width, height)

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, tr("Total HT :", "Subtotal:"))
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, f"{tr('TVA', 'VAT')} ({facture.tva:.0f}%) :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc - facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, tr("Total TTC :", "Total incl. tax:"))
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} {devise}")


    # Horodatage actuel
    now_str = datetime.now().strftime(tr("le %d/%m/%Y à %H:%M", "on %d/%m/%Y at %H:%M"))

    if total_paye >= facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, tr("PAYÉ", "PAID"))
        pdf.setFont("Helvetica-Oblique", 10)  # Italique et plus petit
        pdf.drawString(0, -20, now_str)
        pdf.restoreState()

    elif total_paye < facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, tr("NON PAYÉ", "UNPAID"))
        pdf.setFont("Helvetica-Oblique", 10)
        pdf.drawString(0, -20, now_str)
        pdf.restoreState()


    # Obtenir le moment de la journée
    now = datetime.now()
    heure = now.hour

    if heure < 12:
        moment = tr("Bonne matinée", "Have a good morning")
    elif 12 <= heure < 16:
        moment = tr("Bon après-midi", "Have a good afternoon")
    else:
        moment = tr("Bonne soirée", "Have a good evening")

    message = tr(
        f"Merci pour votre fidélité. – {moment}.",
        f"Thank you for your loyalty. – {moment}.",
    )

    # Définir la police et la couleur
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)  # Gris doux

    # Dessiner le texte centré en bas de page (1.5 cm du bas, centré horizontalement)
    pdf.drawCentredString(10.5 * cm, 1.5 * cm, message)

    pdf.showPage()
    pdf.save()
    pdf_buffer.seek(0)

    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=facture_{facture.id}.pdf"
    })


@router.post("/{facture_id}/email-client")
async def send_facture_to_client_memory(
    facture_id: int,
    invoice_format: Literal["simple", "professional"] = Query(
        "simple",
        alias="template",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    parent_user_id = (
        current_user.parent_user_id
        if not current_user.is_main_user
        else current_user.id
    )
    facture = db.query(Facture).options(
        joinedload(Facture.lignes).joinedload(LigneFacture.produit),
        joinedload(Facture.client),
        joinedload(Facture.fournisseur),
        joinedload(Facture.paiements)
    ).filter(
        Facture.id == facture_id,
        Facture.user_id == parent_user_id,
    ).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    devise = facture.user.devise if hasattr(facture, "user") else ""
    language = language_of(current_user)
    tr = lambda fr, en: translated(language, fr, en)

    if not facture.client or not facture.client.email:
        raise HTTPException(status_code=400, detail="Le client n'a pas d'adresse email")

    if invoice_format == "professional":
        enforce_feature_access(db, current_user, "professional_invoice")
        pdf_path = generate_facture_pdf(facture, db)
        try:
            message = MessageSchema(
                subject=tr(f"Votre facture #{facture.id}", f"Your invoice #{facture.id}"),
                recipients=[facture.client.email],
                body=tr(
                    f"Bonjour {facture.client.nom},\n\nVeuillez trouver en pièce jointe votre facture professionnelle #{facture.id}.\n\nMerci pour votre confiance.",
                    f"Hello {facture.client.nom},\n\nPlease find your professional invoice #{facture.id} attached.\n\nThank you for your trust.",
                ),
                subtype=MessageType.plain,
                attachments=[pdf_path],
            )
            await FastMail(conf).send_message(message)
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
        return {
            "message": (
                f"Facture professionnelle #{facture.id} envoyée à "
                f"{facture.client.email}"
            )
        }

    total_paye = sum(p.montant for p in facture.paiements) if facture.paiements else 0.0

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"{tr('Facture', 'Invoice')} #{facture.id} - {facture.type.value.upper()}")
    y -= 1.2 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"{tr('Date :', 'Date:')} {facture.date_creation.strftime('%d/%m/%Y')}")
    y -= 0.8 * cm

    if facture.client:
        pdf.drawString(2 * cm, y, f"{tr('Client :', 'Customer:')} {facture.client.nom}")
        y -= 0.6 * cm
    if facture.fournisseur:
        pdf.drawString(2 * cm, y, f"{tr('Fournisseur :', 'Supplier:')} {facture.fournisseur.nom}")
        y -= 0.6 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, tr("Produit", "Product"))
    pdf.drawString(9 * cm, y, tr("Qté", "Qty"))
    pdf.drawString(11 * cm, y, "PU")
    pdf.drawString(14 * cm, y, "Total")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 10)

    styles = getSampleStyleSheet()
    styleN = styles["Normal"]
    styleN.fontName = "Helvetica"
    styleN.fontSize = 9
    styleN.leading = 11

    for ligne in facture.lignes:
        produit = ligne.produit
        nom_produit = produit.nom if produit else ligne.description

        # Caractéristiques produit
        caract_display = ""
        if produit and produit.caracteristiques:
            if isinstance(produit.caracteristiques, str):
                caract_display = produit.caracteristiques
            elif isinstance(produit.caracteristiques, dict):
                caract_display = ", ".join(f"{k}: {v}" for k, v in produit.caracteristiques.items())

        unites_concernees = []
        if produit and facture.commande_id:
            unites_concernees = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.commande_vente_id == facture.commande_id
            ).all()
        codes_display = ", ".join(u.tracabilite for u in unites_concernees if u.tracabilite)

        max_length = 150
        if len(codes_display) > max_length:
            codes_display = codes_display[:max_length] + "..."

        # Paragraphe avec retour à la ligne (7.2 cm max)
        text = f"<b>{nom_produit}</b><br/>"
        if caract_display:
            text += f"<i>{tr('Caractéristiques :', 'Details:')}</i> {caract_display}<br/>"
        if codes_display:
            text += f"<i>{tr('Codes :', 'Codes:')}</i> {codes_display}"

        para = Paragraph(text, styleN)
        max_para_width = 7.2 * cm
        w, h = para.wrapOn(pdf, max_para_width, y)
        para.drawOn(pdf, 2.3 * cm, y - h)

        # Qté (centré entre 9.5 et 11)
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(10.25 * cm, y, str(ligne.quantite))

        # PU (aligné à droite à 15.1)
        pdf.drawRightString(15.1 * cm, y, f"{ligne.prix_unitaire:.2f} {devise}")

        # Total (aligné à droite à 18.8)
        pdf.drawRightString(18.8 * cm, y, f"{ligne.total_ligne:.2f} {devise}")

        # Bordures verticales entre colonnes
        pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
        pdf.setLineWidth(0.3)
        pdf.line(9.5 * cm, y, 9.5 * cm, y - h)     # Produit | Qté
        pdf.line(11 * cm, y, 11 * cm, y - h)       # Qté | PU
        pdf.line(15.2 * cm, y, 15.2 * cm, y - h)   # PU | Total

        # Encadrement par ligne
        pdf.setStrokeColorRGB(0.85, 0.85, 0.85)
        pdf.rect(2 * cm, y - h, 17 * cm, h)

        # Ligne horizontale sous la ligne (par colonne, pour plus de clarté)
        line_y = y - h - 0.1 * cm
        pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
        pdf.setLineWidth(0.2)

        # Produit
        pdf.line(2 * cm, line_y, 9.5 * cm, line_y)
        # Qté
        pdf.line(9.5 * cm, line_y, 11 * cm, line_y)
        # PU
        pdf.line(11 * cm, line_y, 15.2 * cm, line_y)
        # Total
        pdf.line(15.2 * cm, line_y, 19 * cm, line_y)

        y -= h + 0.3 * cm

        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm




    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, tr("Total HT :", "Subtotal:"))
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, f"{tr('TVA', 'VAT')} ({facture.tva:.0f}%) :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc - facture.total_ht:.2f} {devise}")
    y -= 0.5 * cm
    pdf.drawRightString(15 * cm, y, tr("Total TTC :", "Total incl. tax:"))
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} {devise}")

    # Horodatage actuel
    now_str = datetime.now().strftime(tr("le %d/%m/%Y à %H:%M", "on %d/%m/%Y at %H:%M"))

    if total_paye >= facture.total_ttc:
        pdf.saveState()
        pdf.setFont("Helvetica-Bold", 36)
        pdf.setFillColorRGB(0.6, 0.1, 0.1)
        pdf.translate(13 * cm, 5 * cm)
        pdf.rotate(25)
        pdf.drawString(0, 0, tr("PAYÉ", "PAID"))
        pdf.setFont("Helvetica-Oblique", 10)  # Italique et plus petit
        pdf.drawString(0, -20, now_str)
        pdf.restoreState()


    # Obtenir le moment de la journée
    now = datetime.now()
    heure = now.hour

    if heure < 12:
        moment = tr("Bonne matinée", "Have a good morning")
    elif 12 <= heure < 18:
        moment = tr("Bon après-midi", "Have a good afternoon")
    else:
        moment = tr("Bonne soirée", "Have a good evening")

    message = tr(
        f"Merci pour votre fidélité. – {moment}.",
        f"Thank you for your loyalty. – {moment}.",
    )

    # Définir la police et la couleur
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)  # Gris doux

    # Dessiner le texte centré en bas de page (1.5 cm du bas, centré horizontalement)
    pdf.drawCentredString(10.5 * cm, 1.5 * cm, message)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f"facture_simple_{facture.id}_",
        suffix=".pdf",
        delete=False,
    ) as pdf_file:
        pdf_file.write(buffer.getvalue())
        pdf_path = pdf_file.name

    try:
        message = MessageSchema(
            subject=tr(f"Votre facture #{facture.id}", f"Your invoice #{facture.id}"),
            recipients=[facture.client.email],
            body=tr(
                f"Bonjour, veuillez trouver en pièce jointe votre facture #{facture.id}.",
                f"Hello, please find your invoice #{facture.id} attached.",
            ),
            subtype=MessageType.plain,
            attachments=[pdf_path]
        )

        await FastMail(conf).send_message(message)
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    return {"message": f"Facture #{facture.id} envoyée à {facture.client.email}"}

