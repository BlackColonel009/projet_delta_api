from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.platypus import PageBreak, Spacer
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.model_enterprise import (
    Enterprise,
    EnterpriseGroup,
    EnterpriseMembership,
    EnterpriseServiceProfile,
)
from app.models.model_client import Client
from app.models.model_commande import CommandeAchat, CommandeVente
from app.models.model_depense import Depense
from app.models.model_depot import Depot
from app.models.model_facture import Facture
from app.models.model_produit import Produit
from app.schemas.enterprise_schema import (
    EnterpriseContextOut,
    EnterpriseCreate,
    EnterpriseOut,
    EnterpriseSelection,
)
from app.services.enterprise_service import (
    SUPPORTED_SERVICES,
    accessible_enterprises,
    resolve_active_enterprise,
    resolve_default_enterprise,
    resolve_membership,
    unique_enterprise_code,
)
from app.services.report_design import ReportDesign, company_owner, money
from app.utils.security import get_active_user, require_main_user
from app.utils.subscription_guard import (
    enforce_feature_access,
    enforce_quota_limit,
)


router = APIRouter(prefix="/enterprises", tags=["Multi-entreprises"])


def _require_group_scope(db: Session, actor) -> EnterpriseMembership:
    membership = resolve_membership(db, actor)
    if membership.scope != "group":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "GROUP_SCOPE_REQUIRED",
                "message": "Cette vue est reservee au proprietaire et au Directeur.",
            },
        )
    return membership


@router.get("/context", response_model=EnterpriseContextOut)
def get_enterprise_context(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    membership = resolve_membership(db, current_user)
    group = db.query(EnterpriseGroup).filter(
        EnterpriseGroup.id == membership.group_id
    ).first()
    enterprises = accessible_enterprises(db, membership)
    _, default_enterprise = resolve_default_enterprise(db, current_user)
    return {
        "group_id": group.id,
        "group_name": group.name,
        "owner_user_id": group.owner_user_id,
        "role": membership.role,
        "scope": membership.scope,
        "can_switch_enterprise": membership.scope == "group",
        "assigned_enterprise_id": membership.enterprise_id,
        "default_enterprise_id": default_enterprise.id,
        "enterprises": enterprises,
    }


@router.post("/context/select", response_model=EnterpriseOut)
def select_enterprise_context(
    data: EnterpriseSelection,
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """Retourne le contexte validé à conserver côté application.

    Les routes métier utiliseront le même validateur lorsqu'elles recevront
    progressivement ``X-Enterprise-ID`` durant la phase de rattachement.
    """
    _, enterprise = resolve_active_enterprise(db, current_user, data.enterprise_id)
    return (
        db.query(Enterprise)
        .options(selectinload(Enterprise.service_profiles))
        .filter(Enterprise.id == enterprise.id)
        .one()
    )


@router.get("/group-dashboard")
def get_group_dashboard(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """Indicateurs consolides, sans fusionner les donnees des entreprises."""
    membership = _require_group_scope(db, current_user)
    enforce_feature_access(db, current_user, "group_dashboard")
    enterprises = db.query(Enterprise).filter(
        Enterprise.group_id == membership.group_id,
        Enterprise.status == "active",
    ).order_by(Enterprise.is_primary.desc(), Enterprise.map_order).all()

    rows = []
    for enterprise in enterprises:
        product_count, stock_quantity = db.query(
            func.count(Produit.id),
            func.coalesce(func.sum(Produit.quantite), 0),
        ).filter(
            Produit.enterprise_id == enterprise.id,
            Produit.date_suppression.is_(None),
        ).one()
        out_of_stock_count = db.query(func.count(Produit.id)).filter(
            Produit.enterprise_id == enterprise.id,
            Produit.date_suppression.is_(None),
            Produit.quantite <= 0,
        ).scalar()
        low_stock_count = db.query(func.count(Produit.id)).filter(
            Produit.enterprise_id == enterprise.id,
            Produit.date_suppression.is_(None),
            Produit.stock_min > 0,
            Produit.quantite > 0,
            Produit.quantite <= Produit.stock_min,
        ).scalar()
        sales_total = db.query(
            func.coalesce(func.sum(CommandeVente.total_ttc), 0)
        ).filter(
            CommandeVente.enterprise_id == enterprise.id,
            func.lower(CommandeVente.statut).notin_(["annulee", "annule", "annulée"]),
        ).scalar()
        purchases_total = db.query(
            func.coalesce(func.sum(CommandeAchat.total_ttc), 0)
        ).filter(
            CommandeAchat.enterprise_id == enterprise.id,
            func.lower(CommandeAchat.statut).notin_(["annulee", "annule", "annulée"]),
        ).scalar()
        expenses_total = db.query(
            func.coalesce(func.sum(Depense.montant), 0)
        ).filter(Depense.enterprise_id == enterprise.id).scalar()
        client_count = db.query(func.count(Client.id)).filter(
            Client.enterprise_id == enterprise.id
        ).scalar()
        open_invoices = db.query(func.count(Facture.id)).filter(
            Facture.enterprise_id == enterprise.id,
            func.lower(Facture.statut).notin_(
                ["paye", "payee", "payé", "payée", "annulee", "annulée"]
            ),
        ).scalar()
        deposit_count = db.query(func.count(Depot.id)).filter(
            Depot.enterprise_id == enterprise.id,
            func.lower(Depot.statut).notin_(["retire", "retiré", "annule", "annulé"]),
        ).scalar()
        rows.append(
            {
                "enterprise_id": enterprise.id,
                "enterprise_name": enterprise.name,
                "enterprise_type": enterprise.enterprise_type,
                "is_primary": enterprise.is_primary,
                "currency": enterprise.currency,
                "product_count": int(product_count or 0),
                "stock_quantity": int(stock_quantity or 0),
                "client_count": int(client_count or 0),
                "sales_total": float(sales_total or 0),
                "purchases_total": float(purchases_total or 0),
                "expenses_total": float(expenses_total or 0),
                "open_invoice_count": int(open_invoices or 0),
                "active_deposit_count": int(deposit_count or 0),
                "out_of_stock_count": int(out_of_stock_count or 0),
                "low_stock_count": int(low_stock_count or 0),
            }
        )

    return {
        "group_id": membership.group_id,
        "enterprise_count": len(rows),
        "totals": {
            "product_count": sum(row["product_count"] for row in rows),
            "stock_quantity": sum(row["stock_quantity"] for row in rows),
            "client_count": sum(row["client_count"] for row in rows),
            "sales_total": sum(row["sales_total"] for row in rows),
            "purchases_total": sum(row["purchases_total"] for row in rows),
            "expenses_total": sum(row["expenses_total"] for row in rows),
            "open_invoice_count": sum(row["open_invoice_count"] for row in rows),
            "active_deposit_count": sum(
                row["active_deposit_count"] for row in rows
            ),
            "out_of_stock_count": sum(
                row["out_of_stock_count"] for row in rows
            ),
            "low_stock_count": sum(row["low_stock_count"] for row in rows),
        },
        "enterprises": rows,
    }


@router.get("/group-dashboard/export")
def export_group_dashboard(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """Rapport PDF consolidé, toujours ventilé par entreprise."""
    enforce_feature_access(db, current_user, "advanced_exports")
    data = get_group_dashboard(current_user=current_user, db=db)
    owner = company_owner(db, current_user)
    design = ReportDesign(owner)
    currency = next(
        (
            row["currency"]
            for row in data["enterprises"]
            if row.get("currency")
        ),
        getattr(owner, "devise", None) or "XOF",
    )
    totals = data["totals"]
    story = design.cover(
        "Tableau de bord général",
        f"Vue consolidée de {data['enterprise_count']} entreprise(s)",
    )
    story += [
        design.p("Synthèse du groupe", "Heading1"),
        design.table(
            ["Indicateur", "Valeur"],
            [
                ["Stock total", totals["stock_quantity"]],
                ["Produits actifs", totals["product_count"]],
                ["Clients", totals["client_count"]],
                ["Ventes cumulées", money(totals["sales_total"], currency)],
                ["Achats cumulés", money(totals["purchases_total"], currency)],
                ["Dépenses", money(totals["expenses_total"], currency)],
                ["Factures ouvertes", totals["open_invoice_count"]],
                ["Consignes actives", totals["active_deposit_count"]],
                ["Produits en rupture", totals["out_of_stock_count"]],
                ["Stocks faibles", totals["low_stock_count"]],
            ],
        ),
        Spacer(1, 18),
        design.p(
            "Les montants restent ventilés par entreprise et ne fusionnent "
            "aucune donnée opérationnelle."
        ),
        PageBreak(),
        design.p("Comparaison des entreprises", "Heading1"),
        design.table(
            [
                "Entreprise",
                "Type",
                "Stock",
                "Ventes",
                "Achats",
                "Factures",
                "Alertes stock",
            ],
            [
                [
                    row["enterprise_name"],
                    row["enterprise_type"],
                    row["stock_quantity"],
                    money(row["sales_total"], row["currency"]),
                    money(row["purchases_total"], row["currency"]),
                    row["open_invoice_count"],
                    row["out_of_stock_count"] + row["low_stock_count"],
                ]
                for row in data["enterprises"]
            ],
            widths=[104, 54, 43, 78, 78, 54, 72],
        ),
    ]
    buffer = BytesIO()
    design.build(buffer, story)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="tableau-de-bord-general.pdf"'
            )
        },
    )


@router.get("/group-search/products")
def search_group_products(
    q: str = Query(min_length=2, max_length=120),
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    membership = _require_group_scope(db, current_user)
    enforce_feature_access(db, current_user, "global_stock_search")
    rows = (
        db.query(Produit, Enterprise)
        .join(Enterprise, Enterprise.id == Produit.enterprise_id)
        .filter(
            Enterprise.group_id == membership.group_id,
            Enterprise.status == "active",
            Produit.date_suppression.is_(None),
            Produit.nom.ilike(f"%{q.strip()}%"),
        )
        .order_by(Produit.quantite.desc(), Produit.nom, Enterprise.map_order)
        .limit(100)
        .all()
    )
    return [
        {
            "product_id": product.id,
            "product_name": product.nom,
            "quantity": int(product.quantite or 0),
            "location": product.emplacement,
            "image_url": product.image_url,
            "enterprise_id": enterprise.id,
            "enterprise_name": enterprise.name,
            "enterprise_type": enterprise.enterprise_type,
            "currency": enterprise.currency,
        }
        for product, enterprise in rows
    ]


@router.post("", response_model=EnterpriseOut, status_code=status.HTTP_201_CREATED)
def create_annex(
    data: EnterpriseCreate,
    current_user=Depends(require_main_user),
    db: Session = Depends(get_db),
):
    membership = resolve_membership(db, current_user)
    if membership.scope != "group" or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Seul le propriétaire peut créer une annexe")

    access = enforce_feature_access(db, current_user, "multi_enterprise")
    enterprise_count = db.query(Enterprise).filter(
        Enterprise.group_id == membership.group_id,
        Enterprise.status == "active",
    ).count()
    enforce_quota_limit(
        access,
        "max_enterprises",
        enterprise_count,
        "entreprises et annexes",
    )

    requested_type = data.enterprise_type
    if data.service_codes:
        legacy_type = (
            "consigne"
            if set(data.service_codes) == {"consigne"}
            else "standard"
        )
        if requested_type and requested_type != legacy_type:
            raise HTTPException(
                status_code=422,
                detail="Le type d'entreprise contredit les anciens profils transmis.",
            )
        requested_type = legacy_type
    requested_type = requested_type or "standard"
    services = {
        "consigne" if requested_type == "consigne" else "gestion_principale"
    }
    unsupported = services - SUPPORTED_SERVICES
    if unsupported:
        raise HTTPException(status_code=422, detail="Profil de service non pris en charge")

    primary = db.query(Enterprise).filter(
        Enterprise.group_id == membership.group_id,
        Enterprise.is_primary.is_(True),
    ).first()
    if not primary:
        raise HTTPException(
            status_code=409,
            detail="L'entreprise principale du groupe doit être restaurée avant de créer une annexe",
        )
    map_order = db.query(Enterprise).filter(
        Enterprise.group_id == membership.group_id
    ).count()
    enterprise = Enterprise(
        group_id=membership.group_id,
        name=data.name.strip(),
        code=unique_enterprise_code(db, membership.group_id, data.code or data.name),
        is_primary=False,
        enterprise_type=requested_type,
        address=data.address,
        phone=data.phone,
        email=data.email,
        logo_url=primary.logo_url,
        app_theme=primary.app_theme,
        theme_mode=primary.theme_mode,
        invoice_color=primary.invoice_color,
        currency=primary.currency,
        timezone=data.timezone,
        map_order=map_order,
    )
    db.add(enterprise)
    db.flush()
    for service_code in sorted(services):
        db.add(
            EnterpriseServiceProfile(
                enterprise_id=enterprise.id,
                service_code=service_code,
                enabled=True,
                configuration_json={},
            )
        )
    db.commit()
    return (
        db.query(Enterprise)
        .options(selectinload(Enterprise.service_profiles))
        .filter(Enterprise.id == enterprise.id)
        .one()
    )
