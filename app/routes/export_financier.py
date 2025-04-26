from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.models.model_depense import Depense
from app.models.model_commande import CommandeVente, CommandeAchat
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from io import BytesIO
import datetime

router = APIRouter(prefix="/export", tags=["Exports Financiers"])

# ➡ Export général en PDF
@router.get("/rapport-complet")
def export_rapport_complet(db: Session = Depends(get_db)):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(2 * cm, y, "Rapport Financier Global")
    y -= 1.5 * cm

    pdf.setFont("Helvetica", 13)
    pdf.drawString(2 * cm, y, "Sommaire :")
    y -= 1 * cm

    pdf.setFont("Helvetica", 11)
    pdf.drawString(2.5 * cm, y, "- Résumé Financier : Page 2")
    y -= 0.8 * cm
    pdf.drawString(2.5 * cm, y, "- Ventes : Page 3")
    y -= 0.8 * cm
    pdf.drawString(2.5 * cm, y, "- Achats : Page 4")
    y -= 0.8 * cm
    pdf.drawString(2.5 * cm, y, "- Dépenses : Page 5")
    
    pdf.setFont("Helvetica-Bold", 16)
    y -= 1.5 * cm

    pdf.setFont("Helvetica", 12)
    pdf.drawString(2 * cm, y, f"Date : {datetime.datetime.now().strftime('%d/%m/%Y')}")
    y -= 2 * cm

    # Résumé général
    total_ventes = db.query(func.sum(CommandeVente.total_ttc)).scalar() or 0
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).scalar() or 0
    total_depenses = db.query(func.sum(Depense.montant)).scalar() or 0
    benefice_net = total_ventes - total_achats - total_depenses

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(2 * cm, y, "Résumé Financier")
    y -= 1 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Total Ventes : {total_ventes:.2f} FCFA")
    y -= 0.6 * cm
    pdf.drawString(2 * cm, y, f"Total Achats : {total_achats:.2f} FCFA")
    y -= 0.6 * cm
    pdf.drawString(2 * cm, y, f"Total Dépenses : {total_depenses:.2f} FCFA")
    y -= 0.6 * cm
    pdf.drawString(2 * cm, y, f"Bénéfice Net : {benefice_net:.2f} FCFA")

    pdf.showPage()

    ### ➡ Détail Ventes
    ventes = db.query(CommandeVente).order_by(CommandeVente.date_commande.desc()).all()
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, height - 2 * cm, "Détail des Ventes")
    y = height - 3 * cm
    pdf.setFont("Helvetica", 10)

    for v in ventes:
        client_nom = v.client.nom if v.client else "Inconnu"
        pdf.drawString(2 * cm, y, f"Vente ID: {v.id} | Client: {client_nom} | Total: {v.total_ttc:.2f} FCFA | Date: {v.date_commande.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.showPage()

    ### ➡ Détail Achats
    achats = db.query(CommandeAchat).order_by(CommandeAchat.date_commande.desc()).all()
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, height - 2 * cm, "Détail des Achats")
    y = height - 3 * cm
    pdf.setFont("Helvetica", 10)

    for a in achats:
        fournisseur_nom = a.fournisseur.nom if a.fournisseur else "Inconnu"
        pdf.drawString(2 * cm, y, f"Achat ID: {a.id} | Fournisseur: {fournisseur_nom} | Total: {a.total_ttc:.2f} FCFA | Date: {a.date_commande.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.showPage()

    ### ➡ Détail Dépenses
    depenses = db.query(Depense).order_by(Depense.date_depense.desc()).all()
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2 * cm, height - 2 * cm, "Détail des Dépenses")
    y = height - 3 * cm
    pdf.setFont("Helvetica", 10)

    for d in depenses:
        pdf.drawString(2 * cm, y, f"Dépense ID: {d.id} | Libelle: {d.libelle} | Montant: {d.montant:.2f} FCFA | Catégorie: {d.categorie} | Date: {d.date_depense.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.save()
    buffer.seek(0)
    

    # ➡ Générer la date du jour
    date_now = datetime.datetime.now().strftime("%d-%m-%Y")

    # ➡ Générer le nom du fichier dynamique
    filename = f"rapport-financier-{date_now}.pdf"
    
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename={filename}"
    })



@router.get("/rapport-depenses")
def export_rapport_depenses(db: Session = Depends(get_db)):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, "Rapport des Dépenses")
    y -= 1.5 * cm

    depenses = db.query(Depense).order_by(Depense.date_depense.desc()).all()
    pdf.setFont("Helvetica", 10)

    for d in depenses:
        pdf.drawString(2 * cm, y, f"Dépense ID: {d.id} | Libelle: {d.libelle} | Montant: {d.montant:.2f} FCFA | Catégorie: {d.categorie} | Date: {d.date_depense.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "inline; filename=rapport_depenses.pdf"
    })

@router.get("/rapport-ventes")
def export_rapport_ventes(db: Session = Depends(get_db)):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, "Rapport des Ventes")
    y -= 1.5 * cm

    ventes = db.query(CommandeVente).order_by(CommandeVente.date_commande.desc()).all()
    pdf.setFont("Helvetica", 10)

    for v in ventes:
        client_nom = v.client.nom if v.client else "Inconnu"
        pdf.drawString(2 * cm, y, f"Vente ID: {v.id} | Client: {client_nom} | Total: {v.total_ttc:.2f} FCFA | Date: {v.date_commande.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "inline; filename=rapport_ventes.pdf"
    })


@router.get("/rapport-achats")
def export_rapport_achats(db: Session = Depends(get_db)):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, "Rapport des Achats")
    y -= 1.5 * cm

    achats = db.query(CommandeAchat).order_by(CommandeAchat.date_commande.desc()).all()
    pdf.setFont("Helvetica", 10)

    for a in achats:
        fournisseur_nom = a.fournisseur.nom if a.fournisseur else "Inconnu"
        pdf.drawString(2 * cm, y, f"Achat ID: {a.id} | Fournisseur: {fournisseur_nom} | Total: {a.total_ttc:.2f} FCFA | Date: {a.date_commande.strftime('%d/%m/%Y')}")
        y -= 0.6 * cm
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm

    pdf.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": "inline; filename=rapport_achats.pdf"
    })
