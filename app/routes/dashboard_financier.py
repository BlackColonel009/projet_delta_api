from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from app.database import get_db
from app.models.model_commande import CommandeVente, CommandeAchat
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from app.models.model_paiement import Paiement
from app.models.model_depense import Depense
from app.services.enterprise_service import actor_enterprise_id
from app.schemas.user_schema import RoleEnum
from app.utils.subscription_guard import require_subscription_feature
from app.utils.permissions import check_role

router = APIRouter(prefix="/dashboard", tags=["Dashboard Financier"])


@router.get(
    "/comparison-access",
    dependencies=[Depends(require_subscription_feature("annual_comparison"))],
)
def comparison_access():
    return {"allowed": True}

# -------------------- Helper Année --------------------
def get_year(year: int | None):
    return year or datetime.utcnow().year

def get_owner_id(current_user):
    # Conserve le nom historique de la variable dans ce module, mais retourne
    # desormais le perimetre financier actif, pas le proprietaire du groupe.
    return actor_enterprise_id(current_user)


def merge_available_years(*year_groups):
    years = set()
    missing = object()
    for group in year_groups:
        for row in group:
            value = getattr(row, "year", missing)
            if value is missing:
                try:
                    value = row[0]
                except (TypeError, IndexError):
                    value = row
            if value is not None:
                years.add(int(value))
    return sorted(years)


def _active_invoice_filters(owner_id: int, selected_year: int):
    return (
        Facture.enterprise_id == owner_id,
        Facture.type == TypeFacture.vente,
        Facture.statut != "annulée",
        extract("year", Facture.date_creation) == selected_year,
    )


def _sales_metrics(db: Session, owner_id: int, selected_year: int):
    """Montants facturés et marge fondée sur le coût figé à la vente."""
    invoice_totals = db.query(
        func.coalesce(func.sum(Facture.total_ht), 0),
        func.coalesce(func.sum(Facture.total_ttc), 0),
    ).filter(*_active_invoice_filters(owner_id, selected_year)).one()

    cost_of_goods = db.query(
        func.coalesce(
            func.sum(LigneFacture.quantite * LigneFacture.cout_achat_unitaire),
            0,
        )
    ).join(Facture, Facture.id == LigneFacture.facture_id).filter(
        *_active_invoice_filters(owner_id, selected_year)
    ).scalar() or 0

    invoiced_ht = float(invoice_totals[0] or 0)
    invoiced_ttc = float(invoice_totals[1] or 0)
    cost_of_goods = float(cost_of_goods)
    return {
        "invoiced_ht": invoiced_ht,
        "invoiced_ttc": invoiced_ttc,
        "cost_of_goods": cost_of_goods,
        "gross_profit": invoiced_ht - cost_of_goods,
    }


def _payment_total(
    db: Session,
    owner_id: int,
    selected_year: int,
    invoice_type: TypeFacture,
) -> float:
    value = db.query(func.coalesce(func.sum(Paiement.montant), 0)).join(
        Facture, Facture.id == Paiement.facture_id
    ).filter(
        Facture.enterprise_id == owner_id,
        Facture.type == invoice_type,
        Facture.statut != "annulée",
        extract("year", Paiement.date_paiement) == selected_year,
    ).scalar() or 0
    return float(value)


def calculate_financial_results(
    *,
    invoiced_ht: float,
    cost_of_goods: float,
    expenses: float,
    collected: float,
    supplier_outflows: float,
):
    gross_profit = float(invoiced_ht) - float(cost_of_goods)
    return {
        "gross_profit": gross_profit,
        "net_profit": gross_profit - float(expenses),
        "net_cash_flow": (
            float(collected) - float(supplier_outflows) - float(expenses)
        ),
    }

# -------------------- Ventes par mois --------------------
@router.get("/ventes-par-mois")
def ventes_par_mois(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)
    ventes = (
        db.query(
            extract('month', Facture.date_creation).label('month'),
            func.sum(Facture.total_ttc).label('total_ventes')
        )
        .filter(*_active_invoice_filters(owner_id, selected_year))
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
    owner_id = get_owner_id(current_user)
    achats = (
        db.query(
            extract('month', CommandeAchat.date_commande).label('month'),
            func.sum(CommandeAchat.total_ttc).label('total_achats')
        )
        .filter(
            CommandeAchat.enterprise_id == owner_id,
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
    owner_id = get_owner_id(current_user)
    depenses = (
        db.query(
            extract('month', Depense.date_depense).label('month'),
            func.sum(Depense.montant).label('total_depenses')
        )
        .filter(
            Depense.enterprise_id == owner_id,
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
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)
    depenses = (
        db.query(
            Depense.categorie,
            func.sum(Depense.montant).label('total_par_categorie')
        )
        .filter(
            Depense.enterprise_id == owner_id,
            extract('year', Depense.date_depense) == selected_year,
        )
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
    owner_id = get_owner_id(current_user)
    metrics = _sales_metrics(db, owner_id, selected_year)

    return {
        "total_ventes_ht": metrics["invoiced_ht"],
        "total_ventes_ttc": metrics["invoiced_ttc"],
        "cout_produits_vendus": metrics["cost_of_goods"],
        "benefice_brut": metrics["gross_profit"],
    }

# -------------------- Bénéfice net --------------------
@router.get("/benefice-net")
def benefice_net(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)

    metrics = _sales_metrics(db, owner_id, selected_year)

    total_depenses = db.query(func.sum(Depense.montant)).filter(
        Depense.enterprise_id == owner_id,
        extract('year', Depense.date_depense) == selected_year
    ).scalar() or 0

    return {
        "total_ventes_ht": metrics["invoiced_ht"],
        "total_ventes_ttc": metrics["invoiced_ttc"],
        "cout_produits_vendus": metrics["cost_of_goods"],
        "total_depenses": float(total_depenses),
        "benefice_net": float(metrics["gross_profit"] - total_depenses),
    }

# -------------------- TVA collectée --------------------
@router.get("/tva-collectee")
def tva_collectee(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)
    total_tva = db.query(
        func.coalesce(func.sum(Facture.total_ttc - Facture.total_ht), 0)
    ).filter(
        Facture.enterprise_id == owner_id,
        Facture.type == TypeFacture.vente,
        Facture.statut == "payée",
        extract("year", Facture.date_creation) == selected_year,
    ).scalar() or 0
    return {"tva_collectee": float(total_tva)}

# -------------------- Clients en retard --------------------
@router.get("/clients-en-retard")
def clients_en_retard(
    year: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)
    factures = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.enterprise_id == owner_id,
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
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    selected_year = get_year(year)
    owner_id = get_owner_id(current_user)
    factures = db.query(Facture).filter(
        Facture.type == "achat",
        Facture.enterprise_id == owner_id,
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
    owner_id = get_owner_id(current_user)

    sales = _sales_metrics(db, owner_id, selected_year)

    # Achats
    total_achats = db.query(func.sum(CommandeAchat.total_ttc)).filter(
        CommandeAchat.enterprise_id == owner_id,
        CommandeAchat.statut == "validée",
        extract('year', CommandeAchat.date_commande) == selected_year
    ).scalar() or 0

    # Dépenses
    total_depenses = db.query(func.sum(Depense.montant)).filter(
        Depense.enterprise_id == owner_id,
        extract('year', Depense.date_depense) == selected_year
    ).scalar() or 0

    # Trésorerie réelle, calculée à la date des paiements.
    encaissements = _payment_total(
        db, owner_id, selected_year, TypeFacture.vente
    )
    decaissements_fournisseurs = _payment_total(
        db, owner_id, selected_year, TypeFacture.achat
    )

    # TVA effectivement collectée sur les factures de vente soldées.
    tva_collectee = db.query(
        func.coalesce(func.sum(Facture.total_ttc - Facture.total_ht), 0)
    ).filter(
        Facture.enterprise_id == owner_id,
        Facture.type == TypeFacture.vente,
        Facture.statut == "payée",
        extract("year", Facture.date_creation) == selected_year,
    ).scalar() or 0

    # Clients en retard
    factures_clients_retard = db.query(Facture).filter(
        Facture.type == "vente",
        Facture.enterprise_id == owner_id,
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
        Facture.enterprise_id == owner_id,
        Facture.statut.notin_(["payée", "annulée"]),
        extract('year', Facture.date_creation) == selected_year
    ).all()
    fournisseurs_a_payer = sum(
        1 for f in factures_fournisseurs
        if f.total_ttc - sum(p.montant for p in f.paiements) > 0
    )

    creances_clients = sum(
        max(float(f.total_ttc or 0) - sum(float(p.montant) for p in f.paiements), 0)
        for f in factures_clients_retard
    )
    dettes_fournisseurs = sum(
        max(float(f.total_ttc or 0) - sum(float(p.montant) for p in f.paiements), 0)
        for f in factures_fournisseurs
    )
    results = calculate_financial_results(
        invoiced_ht=sales["invoiced_ht"],
        cost_of_goods=sales["cost_of_goods"],
        expenses=float(total_depenses),
        collected=encaissements,
        supplier_outflows=decaissements_fournisseurs,
    )

    return {
        # `ventes` reste présent pour compatibilité avec les anciennes apps.
        "ventes": sales["invoiced_ttc"],
        "chiffre_affaires_facture_ht": sales["invoiced_ht"],
        "chiffre_affaires_facture_ttc": sales["invoiced_ttc"],
        "cout_produits_vendus": sales["cost_of_goods"],
        "achats": float(total_achats),
        "depenses": float(total_depenses),
        "benefice_brut": results["gross_profit"],
        "benefice_net": results["net_profit"],
        "encaissements": encaissements,
        "decaissements_fournisseurs": decaissements_fournisseurs,
        "flux_tresorerie_net": results["net_cash_flow"],
        "tva_collectee": float(tva_collectee),
        "clients_en_retard": clients_en_retard,
        "creances_clients": creances_clients,
        "fournisseurs_a_payer": fournisseurs_a_payer,
        "dettes_fournisseurs": dettes_fournisseurs,
    }

# -------------------- Années disponibles --------------------
@router.get("/annees-disponibles")
def annees_disponibles(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    owner_id = get_owner_id(current_user)
    years_ventes = db.query(extract("year", Facture.date_creation).label("year")).filter(
        Facture.enterprise_id == owner_id,
        Facture.type == TypeFacture.vente,
    )
    years_achats = db.query(extract("year", CommandeAchat.date_commande).label("year")).filter(
        CommandeAchat.enterprise_id == owner_id
    )
    years_depenses = db.query(extract("year", Depense.date_depense).label("year")).filter(
        Depense.enterprise_id == owner_id
    )
    years_paiements = db.query(
        extract("year", Paiement.date_paiement).label("year")
    ).join(Facture, Facture.id == Paiement.facture_id).filter(
        Facture.enterprise_id == owner_id
    )

    return merge_available_years(
        years_ventes.distinct().all(),
        years_achats.distinct().all(),
        years_depenses.distinct().all(),
        years_paiements.distinct().all(),
    )


# ******************ROUTES DE V & A ANNULEE**************

@router.get("/vente/annulees", response_model=List[dict])
def ventes_annulees(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    from app.models.model_commande import CommandeVente
    owner_id = get_owner_id(current_user)
    commandes = db.query(CommandeVente).filter(
        CommandeVente.enterprise_id == owner_id,
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
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.comptable]))
):
    from app.models.model_commande import CommandeAchat
    owner_id = get_owner_id(current_user)
    commandes = db.query(CommandeAchat).filter(
        CommandeAchat.enterprise_id == owner_id,
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
