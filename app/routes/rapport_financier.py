from fastapi import APIRouter, Depends
from sqlalchemy import func, extract
from reportlab.lib.utils import ImageReader
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime


from app.database import get_db
from app.models.model_commande import CommandeAchat, CommandeVente
from app.models.model_depense import Depense
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.services import bilan_annuel_service as bilan_annuel
from app.schemas.rapport_financier_schema import RapportAnnuel
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

router = APIRouter(prefix="/rapports", tags=["Rapports Annuels"])

# ➡ Années disponibles
@router.get("/annees-disponibles")
def annees_disponibles(db: Session = Depends(get_db), current_user=Depends(check_role([RoleEnum.admin]))):
    ventes_years = db.query(func.distinct(func.extract('year', CommandeVente.date_commande))).filter(
        CommandeVente.user_id == current_user.id
    ).all()
    achats_years = db.query(func.distinct(func.extract('year', CommandeAchat.date_commande))).filter(
        CommandeAchat.user_id == current_user.id
    ).all()
    depenses_years = db.query(func.distinct(func.extract('year', Depense.date_depense))).filter(
        Depense.user_id == current_user.id
    ).all()
    years = set([int(y[0]) for y in ventes_years + achats_years + depenses_years if y[0]])
    return sorted(list(years))

# ➡ JSON rapport annuel
@router.get("/annuel/{annee}", response_model=RapportAnnuel)
def rapport_annuel(annee: int, db: Session = Depends(get_db), current_user=Depends(check_role([RoleEnum.admin]))):
    user_id = current_user.id
    ventes = bilan_annuel.calcul_ventes(db, annee, user_id)
    achats = bilan_annuel.calcul_achats(db, annee, user_id)
    depenses = bilan_annuel.calcul_depenses(db, annee, user_id)
    benefice_brut, benefice_net = bilan_annuel.calcul_benefices(ventes, achats, depenses)
    clients = bilan_annuel.calcul_clients(db, annee, user_id)
    stock = bilan_annuel.calcul_stock_fin_annee(db, annee, user_id)
    
    return {
        "annee": annee,
        "ventes": ventes,
        "achats": achats,
        "depenses": depenses,
        "benefice_brut": benefice_brut,
        "benefice_net": benefice_net,
        "clients": clients,
        "stock_fin_annee": stock
    }

# ➡ PDF rapport annuel
def get_mensuel_totaux(db: Session, user_id: int, annee: int):
    ventes_mois = db.query(
        extract("month", CommandeVente.date_commande).label("mois"),
        func.sum(CommandeVente.total_ttc).label("total")
    ).filter(
        CommandeVente.user_id == user_id,
        extract("year", CommandeVente.date_commande) == annee
    ).group_by("mois").all()

    achats_mois = db.query(
        extract("month", CommandeAchat.date_commande).label("mois"),
        func.sum(CommandeAchat.total_ttc).label("total")
    ).filter(
        CommandeAchat.user_id == user_id,
        extract("year", CommandeAchat.date_commande) == annee
    ).group_by("mois").all()

    depenses_mois = db.query(
        extract("month", Depense.date_depense).label("mois"),
        func.sum(Depense.montant).label("total")
    ).filter(
        Depense.user_id == user_id,
        extract("year", Depense.date_depense) == annee
    ).group_by("mois").all()

    return {
        "ventes": dict(ventes_mois),
        "achats": dict(achats_mois),
        "depenses": dict(depenses_mois)
    }

import matplotlib
matplotlib.use('Agg')  # ← important : backend non-GUI pour serveur
import matplotlib.pyplot as plt
from io import BytesIO

def creer_graphique_mensuel(data, annee):
    mois = range(1, 13)
    ventes = [data["ventes"].get(m, 0) for m in mois]
    achats = [data["achats"].get(m, 0) for m in mois]
    depenses = [data["depenses"].get(m, 0) for m in mois]

    plt.figure(figsize=(10, 5))
    plt.plot(mois, ventes, marker='o', label='Ventes', color='green')
    plt.plot(mois, achats, marker='o', label='Achats', color='blue')
    plt.plot(mois, depenses, marker='o', label='Dépenses', color='red')
    plt.title(f"Totaux Mensuels {annee}")
    plt.xlabel("Mois")
    plt.ylabel("Montant (FCFA)")
    plt.xticks(mois)
    plt.grid(True)
    plt.legend()

    buffer = BytesIO()
    plt.savefig(buffer, format='PNG', bbox_inches='tight')
    plt.close()
    buffer.seek(0)
    return buffer


def calcul_stock_fin_annee(db: Session, user_id: int):
    produits = db.query(Produit).filter(Produit.user_id == user_id).all()
    stock_dict = {}
    for p in produits:
        stock_total = db.query(UniteProduit).filter(UniteProduit.produit_id == p.id).count()
        stock_disponible = db.query(UniteProduit).filter(
            UniteProduit.produit_id == p.id,
            UniteProduit.statut == "disponible"
        ).count()
        stock_dict[p.nom] = {
            "stock_total": float(stock_total),
            "stock_disponible": float(stock_disponible)
        }
    return stock_dict

from app.models.model_facture import Facture

def get_factures_non_reglees(db: Session, user_id: int, annee: int):
    # Ventes impayées
    ventes_non_reglees = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.user_id == user_id,
        Facture.statut.notin_(["payée", "annulée"]),
        extract('year', Facture.date_creation) == annee
    ).all()

    # Achats impayés
    achats_non_reglees = db.query(Facture).filter(
        Facture.type == "achat",
        Facture.user_id == user_id,
        Facture.statut.notin_(["payée", "annulée"]),
        extract('year', Facture.date_creation) == annee
    ).all()

    return {
        "ventes_non_reglees": ventes_non_reglees,
        "achats_non_reglees": achats_non_reglees
    }


@router.get("/annuel/{annee}/pdf")
def rapport_annuel_pdf(
    annee: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    devise = current_user.devise or "FCFA"

    # Collecte des données
    totaux_mensuels = get_mensuel_totaux(db, parent_user_id, annee)
    stock_fin_annee = calcul_stock_fin_annee(db, parent_user_id)
    factures_non_reglees = get_factures_non_reglees(db, parent_user_id, annee)

    total_ventes = sum(totaux_mensuels["ventes"].values())
    total_achats = sum(totaux_mensuels["achats"].values())
    total_depenses = sum(totaux_mensuels["depenses"].values())
    benefice_net = total_ventes - total_achats - total_depenses

    # Création PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2*cm

    # Page 1 : résumé annuel
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(2*cm, y, f"Rapport Annuel {annee}")
    y -= 2*cm
    pdf.setFont("Helvetica", 12)
    pdf.drawString(2*cm, y, f"Total Ventes : {total_ventes:.2f} {devise}")
    y -= 0.6*cm
    pdf.drawString(2*cm, y, f"Total Achats : {total_achats:.2f} {devise}")
    y -= 0.6*cm
    pdf.drawString(2*cm, y, f"Total Dépenses : {total_depenses:.2f} {devise}")
    y -= 0.6*cm
    pdf.drawString(2*cm, y, f"Bénéfice Net : {benefice_net:.2f} {devise}")
    pdf.showPage()

    # Page 2 : graphique mensuel
    buffer_graph = creer_graphique_mensuel(totaux_mensuels, annee)
    pdf.drawImage(ImageReader(buffer_graph), x=2*cm, y=8*cm, width=16*cm, height=12*cm)
    pdf.showPage()

    # Page 3 : stock final
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2*cm, height-2*cm, "Stock final par produit")
    y = height - 3*cm
    pdf.setFont("Helvetica", 11)
    for nom, data in stock_fin_annee.items():
        pdf.drawString(2*cm, y, f"{nom} | Total: {data['stock_total']:.2f} | Disponible: {data['stock_disponible']:.2f}")
        y -= 0.6*cm
        if y < 3*cm:
            pdf.showPage()
            y = height - 2*cm
    pdf.showPage()

    # Page 4 : factures non réglées
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2*cm, height-2*cm, "Factures Ventes non réglées")
    y = height - 3*cm
    pdf.setFont("Helvetica", 11)
    for v in factures_non_reglees["ventes_non_reglees"]:
        client_nom = v.client.nom if v.client else "Inconnu"
        pdf.drawString(2*cm, y, f"Vente ID: {v.id} | Client: {client_nom} | Total: {v.total_ttc:.2f} {devise} | Date: {v.date_creation.strftime('%d/%m/%Y')}")
        y -= 0.6*cm
        if y < 3*cm:
            pdf.showPage()
            y = height - 2*cm

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(2*cm, y, "Factures Achats non réglées")
    y -= 1*cm
    pdf.setFont("Helvetica", 11)
    for a in factures_non_reglees["achats_non_reglees"]:
        fournisseur_nom = a.fournisseur.nom if a.fournisseur else "Inconnu"
        pdf.drawString(2*cm, y, f"Achat ID: {a.id} | Fournisseur: {fournisseur_nom} | Total: {a.total_ttc:.2f} {devise} | Date: {a.date_creation.strftime('%d/%m/%Y')}")
        y -= 0.6*cm
        if y < 3*cm:
            pdf.showPage()
            y = height - 2*cm

    pdf.save()
    buffer.seek(0)
    filename = f"rapport_annuel_{annee}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={filename}"})