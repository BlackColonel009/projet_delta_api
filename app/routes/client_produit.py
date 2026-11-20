# app/routes/client_produit.py

from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from app.database import get_db
from app.models.model_client_produit import ClientProduit
from app.models.model_client import Client
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from app.schemas.client_produit_schema import ClientProduitOut
from app.schemas.user_schema import RoleEnum
from app.utils.permissions import check_role
from app.services.enterprise_service import enterprise_scope_filter, actor_enterprise_id, actor_owner_id
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

router = APIRouter(prefix="/client-produits", tags=["ClientProduit"])

CLIENT_PRODUCT_ROLES = [
    RoleEnum.admin,
    RoleEnum.directeur,
    RoleEnum.commercial,
    RoleEnum.caissier,
    RoleEnum.comptable,
    RoleEnum.gestionnaire_stock,
    RoleEnum.secretaire,
]


def _client_product_scope(actor):
    scope = ClientProduit.enterprise_id == actor_enterprise_id(actor)
    if getattr(actor, 'active_enterprise_is_primary', False):
        return or_(scope, (ClientProduit.enterprise_id.is_(None)) &
                   ClientProduit.client.has(Client.user_id == actor_owner_id(actor)))
    return scope


def _invoice_line_purchases(db, current_user, client_id, line_id=None):
    """Lit les lignes libres des ventes depuis leur source, sans copie ni doublon."""
    query = db.query(LigneFacture, Facture).join(
        Facture, Facture.id == LigneFacture.facture_id
    ).filter(
        Facture.client_id == client_id,
        enterprise_scope_filter(Facture, current_user),
        Facture.type == TypeFacture.vente,
        or_(Facture.statut.is_(None), Facture.statut.notin_(["annulée", "annulee", "annulé", "annule"])),
        LigneFacture.produit_id.is_(None),
    )
    if line_id is not None:
        query = query.filter(LigneFacture.id == line_id)
    return [
        {
            "id": -line.id, "client_id": invoice.client_id,
            "commande_id": invoice.commande_id, "produit_id": None,
            "note": None, "nom_produit": line.description,
            "categorie_produit": None, "prix_unitaire_backup": line.prix_unitaire,
            "quantite": line.quantite, "prix_unitaire": line.prix_unitaire,
            "date_achat": invoice.date_creation,
        }
        for line, invoice in query.all()
    ]

# 📋 Liste des produits achetés (actifs uniquement)
@router.get("/client/{client_id}", response_model=List[ClientProduitOut])
def get_produits_by_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(CLIENT_PRODUCT_ROLES)),
):
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    items = db.query(ClientProduit).filter(
        ClientProduit.client_id == client_id,
        _client_product_scope(current_user),
        (ClientProduit.note == None) | (ClientProduit.note == "")
    ).all()
    return items + _invoice_line_purchases(db, current_user, client_id)

# 🔍 Détail d’un produit acheté (si actif uniquement)
@router.get("/{id}", response_model=ClientProduitOut)
def get_client_produit(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(CLIENT_PRODUCT_ROLES)),
):
    if id < 0:
        line = db.query(LigneFacture, Facture).join(
            Facture, Facture.id == LigneFacture.facture_id
        ).filter(LigneFacture.id == -id, enterprise_scope_filter(Facture, current_user)).first()
        if line:
            items = _invoice_line_purchases(db, current_user, line[1].client_id, -id)
            if items:
                return items[0]
        raise HTTPException(status_code=404, detail="Achat client introuvable")
    item = db.query(ClientProduit).filter(
        ClientProduit.id == id,
        _client_product_scope(current_user),
        (ClientProduit.note == None) | (ClientProduit.note == "")
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Achat client non trouvé ou inactif")
    return item



# 🗑 Suppression logique d'un lien client-produit
@router.delete("/{id}")
def delete_client_produit(
    id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial])),
):
    if id < 0:
        raise HTTPException(status_code=409, detail="Cette ligne appartient à une facture et ne peut pas être supprimée depuis les achats du client.")
    item = db.query(ClientProduit).filter(
        ClientProduit.id == id,
        _client_product_scope(current_user),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Achat client non trouvé")
    
    item.note = "supprimé"  # ou item.statut = "inactif" si tu préfères
    item.date_modification = datetime.utcnow()  # si tu veux tracer la date
    db.commit()
    
    return {"message": "Liaison client-produit marquée comme supprimée"}


# export pdf
@router.get("/{client_id}/export", response_class=StreamingResponse)
def export_client_produits_pdf(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(CLIENT_PRODUCT_ROLES)),
):
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    produits_all = db.query(ClientProduit).filter(
        ClientProduit.client_id == client_id,
        _client_product_scope(current_user),
    ).all()
    invoice_lines = _invoice_line_purchases(db, current_user, client_id)
    if not produits_all and not invoice_lines:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé pour ce client")

    # Filtres
    from types import SimpleNamespace
    actifs = [p for p in produits_all if not p.note] + [
        SimpleNamespace(**line) for line in invoice_lines
    ]
    rejetes = [p for p in produits_all if p.note == "rejeté"]
    supprimes = [p for p in produits_all if p.note == "supprimé"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2.5 * cm

    def draw_title_block(title, color):
        nonlocal y
        pdf.setFont("Helvetica-Bold", 14)
        pdf.setFillColor(color)
        pdf.drawString(2 * cm, y, title)
        y -= 0.7 * cm
        pdf.setFillColor(colors.black)

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(2 * cm, y, "Nom produit")
        pdf.drawString(8 * cm, y, "Catégorie")
        pdf.drawString(12 * cm, y, "Quantité")
        pdf.drawString(15 * cm, y, "Prix (U)")
        pdf.drawString(18 * cm, y, "Date")
        y -= 0.3 * cm
        pdf.line(2 * cm, y, 19 * cm, y)
        y -= 0.4 * cm

    def draw_produit_rows(produits):
        nonlocal y
        pdf.setFont("Helvetica", 9)
        for p in produits:
            pdf.drawString(2 * cm, y, p.nom_produit or "-")
            pdf.drawString(8 * cm, y, p.categorie_produit or "-")
            pdf.drawRightString(14 * cm, y, str(p.quantite))
            pdf.drawRightString(17 * cm, y, f"{p.prix_unitaire:.2f}")
            pdf.drawRightString(19 * cm, y, p.date_achat.strftime("%d/%m/%Y"))
            y -= 0.5 * cm

            if y < 3 * cm:
                pdf.showPage()
                y = height - 3 * cm
                pdf.setFont("Helvetica", 9)

    # En-tête du document
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"Fiche produits achetés")
    y -= 0.8 * cm
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, y, f"Client : {client.nom}")
    y -= 1 * cm

    # Bloc 1 : Sans note
    if actifs:
        draw_title_block("Produits valides (sans note)", colors.green)
        draw_produit_rows(actifs)

    # Bloc 2 : Rejetés
    if rejetes:
        y -= 0.8 * cm
        draw_title_block("Produits rejetés", colors.orange)
        draw_produit_rows(rejetes)

    # Bloc 3 : Supprimés
    if supprimes:
        y -= 0.8 * cm
        draw_title_block("Produits supprimés", colors.red)
        draw_produit_rows(supprimes)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    filename = f"client_{client.nom.replace(' ', '_').lower()}_produits_{datetime.now().date()}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })

    

    produits = db.query(ClientProduit).filter(ClientProduit.client_id == client_id).all()
    if not produits:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé pour ce client")

    produits_normaux = [p for p in produits if not p.note]
    produits_rejetes = [p for p in produits if p.note == "rejeté"]
    produits_supprimes = [p for p in produits if p.note == "supprimé"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 3 * cm

    def draw_table(pdf, title, produits_list, y, color):
        pdf.setFont("Helvetica-Bold", 13)
        pdf.setFillColor(color)
        pdf.drawString(2 * cm, y, title)
        pdf.setFillColorRGB(0, 0, 0)
        y -= 1 * cm

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
        for p in produits_list:
            pdf.drawString(2 * cm, y, p.nom_produit or "-")
            pdf.drawString(8 * cm, y, p.categorie_produit or "-")
            pdf.drawRightString(14 * cm, y, str(p.quantite))
            pdf.drawRightString(17 * cm, y, f"{p.prix_unitaire:.2f}")
            pdf.drawRightString(19 * cm, y, p.date_achat.strftime("%d/%m/%Y"))
            y -= 0.6 * cm

            if y < 4 * cm:
                pdf.showPage()
                y = height - 3 * cm
                pdf.setFont("Helvetica", 10)

        return y - 1.2 * cm

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(2 * cm, y, f"Produits achetés - Client #{client_id}")
    y -= 2 * cm

    if produits_normaux:
        y = draw_table(pdf, "🟢 Produits actifs (non marqués)", produits_normaux, y, colors.green)

    if produits_rejetes:
        y = draw_table(pdf, "🟠 Produits rejetés", produits_rejetes, y, colors.orange)

    if produits_supprimes:
        y = draw_table(pdf, "🔴 Produits supprimés", produits_supprimes, y, colors.red)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"produits_client_{client_id}_{date_str}.pdf"

    return StreamingResponse(buffer, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })
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
        pdf.drawRightString(17 * cm, y, f"{p.prix_unitaire:.2f}")
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
