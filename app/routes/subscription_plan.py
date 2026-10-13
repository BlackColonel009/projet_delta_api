from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_subscription_plan import SubscriptionPlan
from app.models.model_souscription import Subscription
from app.models.model_user import SubUser
from app.models.model_produit import Produit
from app.models.model_client import Client
from app.models.model_facture import Facture
from app.models.model_facture_depot import FactureDepot
from app.models.model_user import User
from app.schemas.subscription_plan_schema import (
    SubscriptionPlanOut,
    SubscriptionPlanUpdate,
)
from app.utils.security import get_active_user, require_super_user
from app.utils.subscription_guard import resolve_subscription_access


router = APIRouter(prefix="/subscriptions/plans", tags=["Subscription Plans"])


@router.get("/public", response_model=list[SubscriptionPlanOut])
def list_public_subscription_plans(db: Session = Depends(get_db)):
    return (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.monthly_price)
        .all()
    )


@router.get("/access/me")
def get_my_plan_access(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    access = resolve_subscription_access(db, current_user)
    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    month_end = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == access.owner_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )
    usage = {
        "max_sub_users": db.query(SubUser).filter(
            SubUser.parent_user_id == access.owner_id
        ).count(),
        "max_products": db.query(Produit).filter(
            Produit.user_id == access.owner_id,
            Produit.date_suppression.is_(None),
        ).count(),
        "max_clients": db.query(Client).filter(
            Client.user_id == access.owner_id
        ).count(),
        "max_invoices_per_month": (
            db.query(Facture).filter(
                Facture.user_id == access.owner_id,
                Facture.date_creation >= month_start,
                Facture.date_creation < month_end,
            ).count()
            + db.query(FactureDepot).filter(
                FactureDepot.user_id == access.owner_id,
                FactureDepot.date_facture >= month_start,
                FactureDepot.date_facture < month_end,
            ).count()
        ),
    }
    return {
        "plan_code": access.plan_code,
        "plan_name": access.plan_name,
        "features": sorted(access.effective_features()),
        "quotas": {
            "max_sub_users": access.quota("max_sub_users"),
            "max_products": access.quota("max_products"),
            "max_clients": access.quota("max_clients"),
            "max_invoices_per_month": access.quota(
                "max_invoices_per_month"
            ),
        },
        "unlimited": access.unlimited,
        "usage": usage,
        "status": subscription.status if subscription else "active",
        "start_date": subscription.start_date if subscription else None,
        "end_date": (
            None
            if not subscription or access.plan_code == "bronze_free"
            else subscription.end_date
        ),
    }


@router.get("", response_model=list[SubscriptionPlanOut])
def list_active_subscription_plans(
    db: Session = Depends(get_db),
    _: User = Depends(get_active_user),
):
    return (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.monthly_price)
        .all()
    )


@router.get("/admin", response_model=list[SubscriptionPlanOut])
def list_all_subscription_plans(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
):
    return (
        db.query(SubscriptionPlan)
        .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.monthly_price)
        .all()
    )


@router.put("/{plan_code}", response_model=SubscriptionPlanOut)
def update_subscription_plan(
    plan_code: str,
    payload: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
):
    plan = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.code == plan_code)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Offre d’abonnement introuvable")

    values = payload.model_dump()
    values["features"] = [feature.value for feature in payload.features]
    for field, value in values.items():
        setattr(plan, field, value)
    plan.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(plan)
    return plan
