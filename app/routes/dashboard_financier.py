from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from app.database import get_db
from app.models.model_commande import CommandeVente, CommandeAchat
from app.models.model_facture import Facture
from app.models.model_paiement import Paiement
from app.models.model_depense import Depense  # ⚡ N'oublie d'importer le modèle Depense aussi


router = APIRouter(prefix="/dashboard", tags=["Dashboard Financier"])

# ➡ Total des ventes par mois
@router.get("/ventes-par-mois")
def ventes_par_mois(db: Session = Depends(get_db)):
    ventes = (
        db.query(
            extract('year', CommandeVente.date_commande).label('year'),
            extract('month', CommandeVente.date_commande).label('month'),
            func.sum(CommandeVente.total_ttc).label('total_ventes')
        )
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )
    return [
        {"mois": f"{int(v.year)}-{int(v.month):02}", "total_ventes": float(v.total_ventes)}
        for v in ventes
    ]

# ➡ Total des achats par mois
@router.get("/achats-par-mois")
def achats_par_mois(db: Session = Depends(get_db)):
    achats = (
        db.query(
            extract('year', CommandeAchat.date_commande).label('year'),
            extract('month', CommandeAchat.date_commande).label('month'),
            func.sum(CommandeAchat.total_ttc).label('total_achats')
        )
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )
    return [
        {"mois": f"{int(a.year)}-{int(a.month):02}", "total_achats": float(a.total_achats)}
        for a in achats
    ]

# ➡ Bénéfice brut (Ventes - Achats)
@router.get("/benefice-brut")
def benefice_brut(db: Session = Depends(get_db)):
    total_ventes = db.query(func.sum(CommandeVente.total_ttc)).scalar() or 0
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).scalar() or 0
    return {
        "total_ventes": float(total_ventes),
        "total_achats": float(total_achats),
        "benefice_brut": float(total_ventes - total_achats)
    }

# ➡ TVA collectée sur les ventes
@router.get("/tva-collectee")
def tva_collectee(db: Session = Depends(get_db)):
    total_tva = db.query(func.sum(Facture.tva)).scalar() or 0
    return {"tva_collectee": float(total_tva)}

# ➡ Clients en retard de paiement
@router.get("/clients-en-retard")
def clients_en_retard(db: Session = Depends(get_db)):
    factures = db.query(Facture).filter(Facture.type == "vente", Facture.statut != "payée").all()
    result = []
    for f in factures:
        total_paye = sum(p.montant for p in f.paiements)
        reste = f.total_ttc - total_paye
        if reste > 0:
            result.append({
                "facture_id": f.id,
                "client": f.client.nom if f.client else None,
                "total_facture": f.total_ttc,
                "montant_paye": total_paye,
                "reste_a_payer": reste,
                "statut": f.statut
            })
    return result

# ➡ Fournisseurs à payer
@router.get("/fournisseurs-a-payer")
def fournisseurs_a_payer(db: Session = Depends(get_db)):
    factures_achats = db.query(Facture).filter(Facture.type == "achat", Facture.statut != "payée").all()
    result = []
    for f in factures_achats:
        total_paye = sum(p.montant for p in f.paiements)
        reste = f.total_ttc - total_paye
        if reste > 0:
            result.append({
                "facture_id": f.id,
                "fournisseur": f.fournisseur.nom if f.fournisseur else None,
                "total_facture": f.total_ttc,
                "montant_paye": total_paye,
                "reste_a_payer": reste,
                "statut": f.statut
            })
    return result


# ➡ Total des dépenses par mois
@router.get("/depenses-par-mois")
def depenses_par_mois(db: Session = Depends(get_db)):
    depenses = (
        db.query(
            extract('year', Depense.date_depense).label('year'),
            extract('month', Depense.date_depense).label('month'),
            func.sum(Depense.montant).label('total_depenses')
        )
        .group_by('year', 'month')
        .order_by('year', 'month')
        .all()
    )
    return [
        {"mois": f"{int(d.year)}-{int(d.month):02}", "total_depenses": float(d.total_depenses)}
        for d in depenses
    ]

# ➡ Bénéfice net = ventes - achats - dépenses
@router.get("/benefice-net")
def benefice_net(db: Session = Depends(get_db)):
    total_ventes = db.query(func.sum(CommandeVente.total_ttc)).scalar() or 0
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).scalar() or 0
    total_depenses = db.query(func.sum(Depense.montant)).scalar() or 0

    benefice_net = total_ventes - total_achats - total_depenses

    return {
        "total_ventes": float(total_ventes),
        "total_achats": float(total_achats),
        "total_depenses": float(total_depenses),
        "benefice_net": float(benefice_net)
    }

# 📈 Dépenses groupées par catégorie
@router.get("/depenses-par-categorie")
def depenses_par_categorie(db: Session = Depends(get_db)):
    depenses = (
        db.query(
            Depense.categorie,
            func.sum(Depense.montant).label('total_par_categorie')
        )
        .group_by(Depense.categorie)
        .all()
    )
    return [
        {"categorie": d.categorie, "total": float(d.total_par_categorie)}
        for d in depenses
    ]

#afficher tout en un seul
@router.get("/overview")
def dashboard_overview(db: Session = Depends(get_db)):
    # ➡ Total ventes
    total_ventes = db.query(func.sum(CommandeVente.total_ttc)).scalar() or 0

    # ➡ Total achats
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).scalar() or 0

    # ➡ Total dépenses
    total_depenses = db.query(func.sum(Depense.montant)).scalar() or 0

    # ➡ Bénéfice brut
    benefice_brut = total_ventes - total_achats

    # ➡ Bénéfice net
    benefice_net = total_ventes - total_achats - total_depenses

    # ➡ TVA collectée
    tva_collectee = db.query(func.sum(Facture.tva)).scalar() or 0

    # ➡ Clients en retard
    factures_clients_retard = db.query(Facture).filter(Facture.type == "vente", Facture.statut != "payée").count()

    # ➡ Fournisseurs à payer
    factures_fournisseurs_retard = db.query(Facture).filter(Facture.type == "achat", Facture.statut != "payée").count()

    return {
        "ventes": float(total_ventes),
        "achats": float(total_achats),
        "depenses": float(total_depenses),
        "benefice_brut": float(benefice_brut),
        "benefice_net": float(benefice_net),
        "tva_collectee": float(tva_collectee),
        "clients_en_retard": factures_clients_retard,
        "fournisseurs_a_payer": factures_fournisseurs_retard,
    }
