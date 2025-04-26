from app.models.model_facture import Facture, LigneFacture
from sqlalchemy.orm import Session
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.config import conf
from fastapi_mail import FastMail, MessageSchema, MessageType
from reportlab.lib.units import cm


def generate_facture_from_commande(db: Session, commande, commande_type: str):
    """
    🚀 Génère une facture (et son PDF) depuis une commande Vente ou Achat.
    Si commande_type == 'vente', envoie aussi le PDF par email au client.
    """

    # ➡ Créer la Facture en base
    facture = Facture(
        type=commande_type,
        client_id=commande.client_id if commande_type == "vente" else None,
        fournisseur_id=commande.fournisseur_id if commande_type == "achat" else None,
        total_ht=commande.total_ht,
        tva=commande.tva,
        total_ttc=commande.total_ttc
    )
    db.add(facture)
    db.commit()
    db.refresh(facture)

    # ➡ Créer les lignes de facture
    for ligne in commande.lignes:
        ligne_facture = LigneFacture(
            facture_id=facture.id,
            produit_id=ligne.produit_id,
            description=ligne.description,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            total_ligne=ligne.total_ligne
        )
        db.add(ligne_facture)

    db.commit()

    # ➡ Générer le PDF proprement
    pdf_path = generate_facture_pdf(facture)

    # ➡ Si VENTE : envoyer le PDF par email au client
    if commande_type == "vente" and facture.client and facture.client.email:
        fm = FastMail(conf)
        message = MessageSchema(
            subject=f"Votre facture #{facture.id}",
            recipients=[facture.client.email],
            body=f"Bonjour {facture.client.nom},\n\nVeuillez trouver votre facture #{facture.id} d'un montant total de {facture.total_ttc:.2f} {facture.devise}.\nMerci pour votre confiance.",
            subtype=MessageType.plain,
            attachments=[pdf_path]
        )
        try:
            import asyncio
            asyncio.run(fm.send_message(message))
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email : {e}")

    return facture

def generate_facture_pdf(facture):
    """
    🖨 Génère un PDF bien formaté pour la facture, inspiré du modèle facture_pdf.py
    """
    os.makedirs("factures", exist_ok=True)
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
        pdf.drawRightString(13 * cm, y, f"{ligne.prix_unitaire:.2f} €")
        pdf.drawRightString(18 * cm, y, f"{ligne.total_ligne:.2f} €")
        y -= 0.6 * cm
        if y < 4 * cm:
            pdf.showPage()
            y = height - 3 * cm

    y -= 1 * cm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(15 * cm, y, "Total HT :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ht:.2f} €")
    y -= 0.5 * cm

    if facture.tva > 0:
        pdf.drawRightString(15 * cm, y, "TVA (18%) :")
        pdf.drawRightString(19 * cm, y, f"{facture.tva:.2f} €")
        y -= 0.5 * cm

    pdf.drawRightString(15 * cm, y, "Total TTC :")
    pdf.drawRightString(19 * cm, y, f"{facture.total_ttc:.2f} {facture.devise}")

    pdf.showPage()
    pdf.save()

    return pdf_path
