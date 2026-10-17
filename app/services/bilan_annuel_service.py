from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from app.models.model_commande import CommandeAchat
from app.models.model_depense import Depense
from app.models.model_produit import Produit
from app.models.model_client import Client
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from datetime import datetime
from collections import defaultdict

from app.models.model_unite_produit import UniteProduit

def calcul_ventes(db: Session, year: int, user_id: int):
    ventes = (
        db.query(
            extract('month', Facture.date_creation).label('month'),
            func.sum(Facture.total_ttc).label('total')
        )
        .filter(
            Facture.enterprise_id == user_id,
            Facture.type == TypeFacture.vente,
            Facture.statut != "annulée",
            extract('year', Facture.date_creation) == year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    par_mois = [{"mois": f"{year}-{int(v.month):02}", "total": float(v.total)} for v in ventes]
    total = sum(v["total"] for v in par_mois)
    return {"par_mois": par_mois, "total": total}

def calcul_achats(db: Session, year: int, user_id: int):
    achats = (
        db.query(
            extract('month', CommandeAchat.date_commande).label('month'),
            func.sum(CommandeAchat.total_ttc).label('total')
        )
        .filter(
            CommandeAchat.enterprise_id == user_id,
            CommandeAchat.statut == "validée",
            extract('year', CommandeAchat.date_commande) == year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    par_mois = [{"mois": f"{year}-{int(a.month):02}", "total": float(a.total)} for a in achats]
    total = sum(a["total"] for a in par_mois)
    return {"par_mois": par_mois, "total": total}

def calcul_depenses(db: Session, year: int, user_id: int):
    depenses = (
        db.query(
            extract('month', Depense.date_depense).label('month'),
            func.sum(Depense.montant).label('total')
        )
        .filter(
            Depense.enterprise_id == user_id,
            extract('year', Depense.date_depense) == year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    par_mois = [{"mois": f"{year}-{int(d.month):02}", "total": float(d.total)} for d in depenses]
    total = sum(d["total"] for d in par_mois)
    return {"par_mois": par_mois, "total": total}

def calcul_cout_produits_vendus(db: Session, year: int, user_id: int) -> float:
    value = db.query(
        func.coalesce(
            func.sum(LigneFacture.quantite * LigneFacture.cout_achat_unitaire),
            0,
        )
    ).join(Facture, Facture.id == LigneFacture.facture_id).filter(
        Facture.enterprise_id == user_id,
        Facture.type == TypeFacture.vente,
        Facture.statut != "annulée",
        extract('year', Facture.date_creation) == year,
    ).scalar() or 0
    return float(value)


def calcul_total_ventes_ht(db: Session, year: int, user_id: int) -> float:
    value = db.query(func.coalesce(func.sum(Facture.total_ht), 0)).filter(
        Facture.enterprise_id == user_id,
        Facture.type == TypeFacture.vente,
        Facture.statut != "annulée",
        extract('year', Facture.date_creation) == year,
    ).scalar() or 0
    return float(value)


def calcul_benefices(ventes_ht, cout_produits_vendus, depenses):
    benefice_brut = ventes_ht - cout_produits_vendus
    benefice_net = benefice_brut - depenses["total"]
    return benefice_brut, benefice_net

def calcul_clients(db: Session, year: int, user_id: int):
    # Nouveaux clients de l'année
    nouveaux = db.query(Client).filter(
        Client.enterprise_id == user_id,
        extract('year', Client.date_creation) == year
    ).count()
    # Impayés (toutes factures non réglées)
    impayes = db.query(Facture).filter(
        Facture.enterprise_id == user_id,
        Facture.statut.notin_(["payée", "annulée"])
    ).count()
    return {"nouveaux": nouveaux, "impayes": impayes}

def calcul_stock_fin_annee(db: Session, year: int, user_id: int):
    produits = db.query(Produit).filter(Produit.enterprise_id == user_id).all()
    stock_dict = {}
    for p in produits:
        stock_dispo = db.query(UniteProduit).filter(
            UniteProduit.produit_id == p.id,
            UniteProduit.enterprise_id == user_id,
            UniteProduit.statut == "disponible"
        ).count()
        stock_dict[p.nom] = float(stock_dispo)  # <- juste la quantité disponible
    return stock_dict

