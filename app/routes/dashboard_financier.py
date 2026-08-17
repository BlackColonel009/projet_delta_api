from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, text
from datetime import datetime
from app.database import get_db
from app.models.model_commande import CommandeVente, CommandeAchat, LigneCommandeVente
from app.models.model_facture import Facture
from app.models.model_paiement import Paiement
from app.models.model_depense import Depense
from app.models.model_produit import Produit
from app.schemas.user_schema import RoleEnum
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router = APIRouter(prefix="/dashboard", tags=["Dashboard Financier"])

# -------------------- Helper Année --------------------
def get_year(year: int | None):
    return year or datetime.utcnow().year

# -------------------- Ventes par mois --------------------
@router.get("/ventes-par-mois")
def ventes_par_mois(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    ventes = (
        db.query(
            extract('month', CommandeVente.date_commande).label('month'),
            func.sum(CommandeVente.total_ttc).label('total_ventes')
        )
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée",
            extract('year', CommandeVente.date_commande) == selected_year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    return [
        {"mois": f"{selected_year}-{int(v.month):02}", "total_ventes": float(v.total_ventes)}
        for v in ventes
    ]

# -------------------- Achats par mois --------------------
@router.get("/achats-par-mois")
def achats_par_mois(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    achats = (
        db.query(
            extract('month', CommandeAchat.date_commande).label('month'),
            func.sum(CommandeAchat.total_ttc).label('total_achats')
        )
        .filter(
            CommandeAchat.user_id == current_user.id,
            CommandeAchat.statut == "validée",
            extract('year', CommandeAchat.date_commande) == selected_year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    return [
        {"mois": f"{selected_year}-{int(a.month):02}", "total_achats": float(a.total_achats)}
        for a in achats
    ]

# -------------------- Dépenses par mois --------------------
@router.get("/depenses-par-mois")
def depenses_par_mois(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    depenses = (
        db.query(
            extract('month', Depense.date_depense).label('month'),
            func.sum(Depense.montant).label('total_depenses')
        )
        .filter(
            Depense.user_id == current_user.id,
            extract('year', Depense.date_depense) == selected_year
        )
        .group_by('month')
        .order_by('month')
        .all()
    )
    return [
        {"mois": f"{selected_year}-{int(d.month):02}", "total_depenses": float(d.total_depenses)}
        for d in depenses
    ]

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

# -------------------- Bénéfice brut --------------------
@router.get("/benefice-brut")
def benefice_brut(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    lignes = (
        db.query(LigneCommandeVente)
        .join(CommandeVente)
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée",
            extract('year', CommandeVente.date_commande) == selected_year
        )
        .all()
    )

    total_ventes = 0
    cout_achats_estimes = 0

    for ligne in lignes:
        total_ventes += ligne.total_ligne
        produit = db.query(Produit).filter(Produit.id == ligne.produit_id).first()
        prix_achat = produit.prix_achat if produit and produit.prix_achat is not None else 0
        cout_achats_estimes += prix_achat * ligne.quantite

    return {
        "total_ventes": float(total_ventes),
        "cout_achats_estimes": float(cout_achats_estimes),
        "benefice_brut": float(total_ventes - cout_achats_estimes)
    }

# -------------------- Bénéfice net --------------------
@router.get("/benefice-net")
def benefice_net(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)

    lignes = (
        db.query(LigneCommandeVente)
        .join(CommandeVente)
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée",
            extract('year', CommandeVente.date_commande) == selected_year
        )
        .all()
    )

    total_ventes = 0
    cout_achat_total = 0
    for ligne in lignes:
        total_ventes += ligne.total_ligne
        produit = db.query(Produit).filter(Produit.id == ligne.produit_id).first()
        cout_unitaire = produit.prix_achat if produit and produit.prix_achat else 0
        cout_achat_total += cout_unitaire * ligne.quantite

    total_depenses = db.query(func.sum(Depense.montant)).filter(
        Depense.user_id == current_user.id,
        extract('year', Depense.date_depense) == selected_year
    ).scalar() or 0

    return {
        "total_ventes": float(total_ventes),
        "cout_achats_estimes": float(cout_achat_total),
        "total_depenses": float(total_depenses),
        "benefice_net": float(total_ventes - cout_achat_total - total_depenses)
    }

# -------------------- TVA collectée --------------------
@router.get("/tva-collectee")
def tva_collectee(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    query = text("""
        SELECT SUM(f.tva)
        FROM factures f
        JOIN commandes_ventes cv ON f.commande_id = cv.id
        WHERE f.user_id = :user_id
        AND f.type = 'vente'
        AND f.statut = 'payée'
        AND cv.statut = 'validée'
        AND EXTRACT(YEAR FROM f.date_creation) = :year
    """)
    total_tva = db.execute(query, {"user_id": current_user.id, "year": selected_year}).scalar() or 0
    return {"tva_collectee": float(total_tva)}

# -------------------- Clients en retard --------------------
@router.get("/clients-en-retard")
def clients_en_retard(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    selected_year = get_year(year)
    factures = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.user_id == current_user.id,
        Facture.statut.notin_(["payée", "annulée"]),
        extract('year', Facture.date_creation) == selected_year
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

# -------------------- Fournisseurs à payer --------------------
@router.get("/fournisseurs-a-payer")
def fournisseurs_a_payer(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    selected_year = get_year(year)
    factures = db.query(Facture).filter(
        Facture.type == "achat",
        Facture.user_id == current_user.id,
        Facture.statut != "payée",
        extract('year', Facture.date_creation) == selected_year
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

# -------------------- Overview --------------------
@router.get("/overview")
def dashboard_overview(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)

    # Ventes
    lignes = (
        db.query(LigneCommandeVente)
        .join(CommandeVente)
        .filter(
            CommandeVente.user_id == current_user.id,
            CommandeVente.statut == "validée",
            extract('year', CommandeVente.date_commande) == selected_year
        )
        .all()
    )
    total_ventes = sum(l.total_ligne for l in lignes)
    cout_achat_total = sum(
        (db.query(Produit).filter(Produit.id == l.produit_id).first().prix_achat or 0) * l.quantite
        for l in lignes
    )

    # Achats
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).filter(
        CommandeAchat.user_id == current_user.id,
        CommandeAchat.statut == "validée",
        extract('year', CommandeAchat.date_commande) == selected_year
    ).scalar() or 0

    # Dépenses
    total_depenses = db.query(func.sum(Depense.montant)).filter(
        Depense.user_id == current_user.id,
        extract('year', Depense.date_depense) == selected_year
    ).scalar() or 0

    # TVA
    query = text("""
        SELECT SUM(f.tva)
        FROM factures f
        JOIN commandes_ventes cv ON f.commande_id = cv.id
        WHERE f.user_id = :user_id
        AND f.type = 'vente'
        AND f.statut = 'payée'
        AND cv.statut = 'validée'
        AND EXTRACT(YEAR FROM f.date_creation) = :year
    """)
    tva_collectee = db.execute(query, {"user_id": current_user.id, "year": selected_year}).scalar() or 0

    # Clients en retard
    factures_clients_retard = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.user_id == current_user.id,
        Facture.statut.notin_(["payée", "annulée"]),
        extract('year', Facture.date_creation) == selected_year
    ).all()
    clients_en_retard = sum(
        1 for f in factures_clients_retard
        if f.total_ttc - sum(p.montant for p in f.paiements) > 0
    )

    # Fournisseurs à payer
    factures_fournisseurs = db.query(Facture).filter(
        Facture.type == "achat",
        Facture.user_id == current_user.id,
        Facture.statut != "payée",
        extract('year', Facture.date_creation) == selected_year
    ).all()
    fournisseurs_a_payer = sum(
        1 for f in factures_fournisseurs
        if f.total_ttc - sum(p.montant for p in f.paiements) > 0
    )

    return {
        "ventes": float(total_ventes),
        "achats": float(total_achats),
        "depenses": float(total_depenses),
        "benefice_brut": float(total_ventes - cout_achat_total),
        "benefice_net": float(total_ventes - cout_achat_total - total_depenses),
        "tva_collectee": float(tva_collectee),
        "clients_en_retard": clients_en_retard,
        "fournisseurs_a_payer": fournisseurs_a_payer,
    }

# -------------------- Années disponibles --------------------
@router.get("/annees-disponibles")
def annees_disponibles(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    years_ventes = db.query(extract("year", CommandeVente.date_commande).label("year")).filter(
        CommandeVente.user_id == current_user.id
    )
    years_achats = db.query(extract("year", CommandeAchat.date_commande).label("year")).filter(
        CommandeAchat.user_id == current_user.id
    )
    years_depenses = db.query(extract("year", Depense.date_depense).label("year")).filter(
        Depense.user_id == current_user.id
    )

    years = years_ventes.union(years_achats).union(years_depenses).distinct().order_by("year").all()
    return [int(y.year) for y in years if y.year]


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
