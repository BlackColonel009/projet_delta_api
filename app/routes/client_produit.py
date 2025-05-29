# app/routes/client_produit.py

from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_client_produit import ClientProduit
from app.schemas.client_produit_schema import ClientProduitOut
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

router = APIRouter(prefix="/client-produits", tags=["ClientProduit"])

# 📋 Liste des produits achetés par un client
@router.get("/client/{client_id}", response_model=List[ClientProduitOut])
def get_produits_by_client(client_id: int, db: Session = Depends(get_db)):
    return db.query(ClientProduit).filter(ClientProduit.client_id == client_id).all()

# 🔍 Détail d’un produit acheté
@router.get("/{id}", response_model=ClientProduitOut)
def get_client_produit(id: int, db: Session = Depends(get_db)):
    item = db.query(ClientProduit).filter(ClientProduit.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Achat client non trouvé")
    return item

# 🗑 Supprimer un lien client-produit
@router.delete("/{id}")
def delete_client_produit(id: int, db: Session = Depends(get_db)):
    item = db.query(ClientProduit).filter(ClientProduit.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Achat client non trouvé")
    db.delete(item)
    db.commit()
    return {"message": "Liaison client-produit supprimée"}

# export pdf
@router.get("/{client_id}/export", response_class=StreamingResponse)
def export_client_produits_pdf(client_id: int, db: Session = Depends(get_db)):
    produits = db.query(ClientProduit).filter(ClientProduit.client_id == client_id).all()
    if not produits:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé pour ce client")

    # 📄 Génération PDF en mémoire
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 3 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"Produits achetés - Client #{client_id}")
    y -= 1.5 * cm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Nom produit")
    pdf.drawString(8 * cm, y, "Catégorie")
    pdf.drawString(12 * cm, y, "Quantité")
    pdf.drawString(15 * cm, y, "Prix (U)")
    pdf.drawString(18 * cm, y, "Date")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, 19 * cm, y)
    y -= 0.5 * cm

    pdf.setFont("Helvetica", 10)
    for p in produits:
        pdf.drawString(2 * cm, y, p.nom_produit or "-")
        pdf.drawString(8 * cm, y, p.categorie_produit or "-")
        pdf.drawRightString(14 * cm, y, str(p.quantite))
        pdf.drawRightString(17 * cm, y, f"{p.prix_unitaire:.2f} €")
        pdf.drawRightString(19 * cm, y, p.date_achat.strftime("%d/%m/%Y"))
        y -= 0.6 * cm

        if y < 3 * cm:
            pdf.showPage()
            y = height - 3 * cm
            pdf.setFont("Helvetica", 10)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"produits_client_{client_id}_{date_str}.pdf"

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })