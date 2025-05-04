from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import json
from PIL import Image
from app.models.model_produit import Produit
from app.models.model_commande import CommandeVente, LigneCommandeVente
from datetime import datetime
from app.schemas.scanqr_schema import ScanQRInput, ProduitCreateViaScan, VenteTracabiliteInput
from app.database import get_db
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router = APIRouter(prefix="/scanqr", tags=["QR-Code"])

@router.post("/generate_qr")
def generate_qr_codes(
    nombre: int = Query(..., description="Nombre de QR Codes à générer"),
    prefixe: str = Query("TRAC-", description="Préfixe pour la tracabilité"),
    modele_nom_produit: str = Query("Produit", description="Modèle de nom de produit de base"),
    societe: str = Query(..., description="Nom de la société associée"),
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"]))
):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    x, y = 2 * cm, height - 3 * cm

    for i in range(1, nombre + 1):
        tracabilite = f"{prefixe}{str(i).zfill(5)}"
        qr_data = {
            "nom_produit": f"{modele_nom_produit}-{i}",
            "tracabilite": tracabilite,
            "societe": societe
        }
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")

        img_buffer = BytesIO()
        img_qr.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        img_pil = Image.open(img_buffer)

        pdf.drawInlineImage(img_pil, x, y, 4*cm, 4*cm)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x, y - 0.5*cm, f"{qr_data['nom_produit']}")

        x += 6 * cm
        if x > width - 6 * cm:
            x = 2 * cm
            y -= 6 * cm
            if y < 4 * cm:
                pdf.showPage()
                x, y = 2 * cm, height - 3 * cm

    pdf.save()
    buffer.seek(0)
    filename = f"qr-produits-{datetime.now().strftime('%d-%m-%Y')}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.post("/scan_and_check")
def scan_and_check(data: ScanQRInput, db: Session = Depends(get_db)):
    produit = db.query(Produit).filter(Produit.tracabilite == data.tracabilite).first()
    if produit:
        return {
            "action": "vente",
            "produit_id": produit.id,
            "nom": produit.nom,
            "prix_vente": produit.prix_vente,
            "quantite": produit.quantite,
            "message": "Produit trouvé. Souhaitez-vous lancer une vente ?"
        }
    else:
        return {
            "action": "ajout",
            "pre_remplir": {
                "nom": data.nom_produit,
                "tracabilite": data.tracabilite,
                "societe": data.societe
            },
            "message": "Produit non trouvé. Voulez-vous l'ajouter ?"
        }

@router.post("/confirm_add_after_scan")
def confirm_add_after_scan(
    data: ProduitCreateViaScan,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"]))
):
    produit_existant = db.query(Produit).filter(Produit.tracabilite == data.tracabilite).first()
    if produit_existant:
        raise HTTPException(status_code=400, detail="Un produit avec cette tracabilité existe déjà.")

    nouveau_produit = Produit(
        nom=data.nom,
        categorie_id=data.categorie_id,
        prix_achat=data.prix_achat,
        prix_vente=data.prix_vente,
        quantite=data.quantite,
        couleur=data.couleur,
        commentaire=data.commentaire,
        tracabilite=data.tracabilite,
        emplacement="magasin",
        date_creation=datetime.utcnow(),
        date_modification=datetime.utcnow()
    )
    db.add(nouveau_produit)
    db.commit()
    db.refresh(nouveau_produit)

    return {
        "message": "Produit ajouté avec succès après scan.",
        "produit_id": nouveau_produit.id,
        "nom": nouveau_produit.nom
    }

@router.get("/find_by_tracabilite/{tracabilite}")
def find_product_by_tracabilite(tracabilite: str, db: Session = Depends(get_db)):
    produit = db.query(Produit).filter(Produit.tracabilite == tracabilite).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé avec cette tracabilité.")
    return {
        "produit_id": produit.id,
        "nom": produit.nom,
        "categorie_id": produit.categorie_id,
        "prix_achat": produit.prix_achat,
        "prix_vente": produit.prix_vente,
        "quantite": produit.quantite,
        "etat": produit.etat,
        "emplacement": produit.emplacement,
        "tracabilite": produit.tracabilite
    }

@router.post("/creer_par_tracabilite")
def creer_vente_par_tracabilite(
    data: VenteTracabiliteInput,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock"]))
):
    produit = db.query(Produit).filter(Produit.tracabilite == data.tracabilite).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé.")

    if produit.quantite < data.quantite:
        raise HTTPException(status_code=400, detail="Stock insuffisant pour cette vente.")

    prix_unitaire = produit.prix_vente
    total_ht = prix_unitaire * data.quantite
    tva = 18 if data.tva_appliquee else 0
    total_ttc = total_ht * (1 + tva / 100)

    commande = CommandeVente(
        client_id=data.client_id if data.client_id else 1,
        date_commande=datetime.utcnow(),
        total_ht=total_ht,
        total_ttc=total_ttc,
        tva=tva,
        tva_appliquee=data.tva_appliquee,
        statut="payée"
    )
    db.add(commande)
    db.commit()
    db.refresh(commande)

    ligne = LigneCommandeVente(
        commande_id=commande.id,
        produit_id=produit.id,
        description=produit.nom,
        quantite=data.quantite,
        prix_unitaire=prix_unitaire,
        total_ligne=total_ht
    )
    db.add(ligne)
    produit.quantite -= data.quantite
    db.commit()

    return {
        "message": "Vente réalisée avec succès.",
        "commande_id": commande.id,
        "produit": produit.nom,
        "quantite_vendue": data.quantite,
        "total_ht": round(total_ht, 2),
        "total_ttc": round(total_ttc, 2),
        "stock_restant": produit.quantite
    }
