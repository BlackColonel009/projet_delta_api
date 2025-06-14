from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from app.database import get_db
from app.models.model_commande import CommandeVente, CommandeAchat
from app.models.model_facture import Facture
from app.models.model_paiement import Paiement
from app.models.model_depense import Depense
from app.schemas.user_schema import RoleEnum
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router = APIRouter(prefix="/dashboard", tags=["Dashboard Financier"])

# ➡ Total des ventes par mois
@router.get("/ventes-par-mois")
def ventes_par_mois(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    ventes = (
        db.query(
            extract('year', CommandeVente.date_commande).label('year'),
            extract('month', CommandeVente.date_commande).label('month'),
            func.sum(CommandeVente.total_ttc).label('total_ventes')
        )
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée"
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
def achats_par_mois(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    achats = (
        db.query(
            extract('year', CommandeAchat.date_commande).label('year'),
            extract('month', CommandeAchat.date_commande).label('month'),
            func.sum(CommandeAchat.total_ttc).label('total_achats')
        )
        . filter(
            CommandeAchat.user_id == current_user.id,
            CommandeAchat.statut == "validée"
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
def benefice_brut(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    from app.models.model_commande import CommandeVente, LigneCommandeVente
    from app.models.model_produit import Produit

    # 1. Récupérer toutes les lignes de commande validées
    lignes = (
        db.query(LigneCommandeVente)
        .join(CommandeVente)
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée"
        )
        .all()
    )

    total_ventes = 0
    cout_achats_estimes = 0

    # 2. Calcule du total TTC & coût des achats (basé sur le prix_achat unitaire)
    for ligne in lignes:
        total_ventes += ligne.total_ligne
        prix_achat = ligne.produit.prix_achat if ligne.produit and ligne.produit.prix_achat else 0
        cout_achats_estimes += prix_achat * ligne.quantite

    return {
        "total_ventes": float(total_ventes),
        "cout_achats_estimes": float(cout_achats_estimes),
        "benefice_brut": float(total_ventes - cout_achats_estimes)
    }


# ➡ TVA collectée sur les ventes
@router.get("/tva-collectee")
def tva_collectee(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    total_tva = (
        db.query(func.sum(Facture.tva))
        .join(CommandeVente, Facture.commande_id == CommandeVente.id)
        .filter(
            Facture.user_id == current_user.id,
            Facture.type == "vente",
            Facture.statut == "payée",
            CommandeVente.statut == "validée"
        )
        .scalar()
        or 0
    )
    return {"tva_collectee": float(total_tva)}


# ➡ Clients en retard de paiement
@router.get("/clients-en-retard")
def clients_en_retard(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    factures = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.user_id == current_user.id,
        Facture.statut != "payée"
    ).all()

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
def fournisseurs_a_payer(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier]))
):
    factures = db.query(Facture).filter(
        Facture.type == "achat",
        Facture.user_id == current_user.id,
        Facture.statut != "payée"
    ).all()

    result = []
    for f in factures:
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
def depenses_par_mois(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    depenses = (
        db.query(
            extract('year', Depense.date_depense).label('year'),
            extract('month', Depense.date_depense).label('month'),
            func.sum(Depense.montant).label('total_depenses')
        )
        .filter(Depense.user_id == current_user.id)
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
def benefice_net(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    from app.models.model_commande import CommandeVente, LigneCommandeVente
    from app.models.model_produit import Produit

    # 1. Ventes validées uniquement
    ventes = (
        db.query(LigneCommandeVente)
        .join(CommandeVente)
        .filter(CommandeVente.user_id == current_user.id, CommandeVente.statut == "validée")
        .all()
    )

    # 2. Calcul du total_ventes et coût des produits vendus
    total_ventes = 0
    cout_achat_total = 0

    for ligne in ventes:
        total_ventes += ligne.total_ligne
        cout_unitaire = ligne.produit.prix_achat if ligne.produit and ligne.produit.prix_achat else 0
        cout_achat_total += cout_unitaire * ligne.quantite

    # 3. Dépenses classiques
    total_depenses = db.query(func.sum(Depense.montant)).filter(Depense.user_id == current_user.id).scalar() or 0

    # 4. Résultat
    return {
        "total_ventes": float(total_ventes),
        "cout_achats_estimes": float(cout_achat_total),
        "total_depenses": float(total_depenses),
        "benefice_net": float(total_ventes - cout_achat_total - total_depenses)
    }


# ➡ Dépenses par catégorie
@router.get("/depenses-par-categorie")
def depenses_par_categorie(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    depenses = (
        db.query(
            Depense.categorie,
            func.sum(Depense.montant).label('total_par_categorie')
        )
        .filter(Depense.user_id == current_user.id)
        .group_by(Depense.categorie)
        .all()
    )
    return [
        {"categorie": d.categorie, "total": float(d.total_par_categorie)}
        for d in depenses
    ]

# 🔎 Tout le dashboard résumé
@router.get("/overview")
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    total_ventes = db.query(func.sum(CommandeVente.total_ttc)).filter(
        CommandeVente.user_id == current_user.id,
        CommandeVente.statut == "validée"
    ).scalar() or 0

    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).filter(
        CommandeAchat.user_id == current_user.id,
        CommandeAchat.statut == "validée"
    ).scalar() or 0

    total_depenses = db.query(func.sum(Depense.montant)).filter(Depense.user_id == current_user.id).scalar() or 0
    benefice_brut = total_ventes - total_achats
    benefice_net = total_ventes - total_achats - total_depenses
    tva_collectee = db.query(func.sum(Facture.tva)).filter(Facture.user_id == current_user.id).scalar() or 0
    factures_clients_retard = db.query(Facture).filter(Facture.type == "vente", Facture.user_id == current_user.id, Facture.statut != "payée").count()
    factures_fournisseurs_retard = db.query(Facture).filter(Facture.type == "achat", Facture.user_id == current_user.id, Facture.statut != "payée").count()

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
# ******************ROUTES DE V & A ANNULEE**************

@router.get("/vente/annulees", response_model=List[dict])
def ventes_annulees(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from app.models.model_commande import CommandeVente
    commandes = db.query(CommandeVente).filter(
        CommandeVente.user_id == current_user.id,
        CommandeVente.statut == "annulée"
    ).order_by(CommandeVente.date_commande.desc()).all()

    return [
        {
            "id": c.id,
            "client_id": c.client_id,
            "date_commande": c.date_commande,
            "total_ttc": c.total_ttc,
            "statut": c.statut
        } for c in commandes
    ]

@router.get("/achat/annulees", response_model=List[dict])
def achats_annules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from app.models.model_commande import CommandeAchat
    commandes = db.query(CommandeAchat).filter(
        CommandeAchat.user_id == current_user.id,
        CommandeAchat.statut == "annulée"
    ).order_by(CommandeAchat.date_commande.desc()).all()

    return [
        {
            "id": c.id,
            "fournisseur_id": c.fournisseur_id,
            "date_commande": c.date_commande,
            "total_ttc": c.total_ttc,
            "statut": c.statut
        } for c in commandes
    ]
