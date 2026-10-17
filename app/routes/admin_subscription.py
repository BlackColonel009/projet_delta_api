from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_subscription_plan import SubscriptionPlan
from app.models.model_souscription import Subscription
from app.models.model_user import User
from app.schemas.subscription_schema import GrantSubscriptionRequest
from app.services.subscription_service import (
    activate_subscription,
)
from app.utils.security import get_active_user, require_super_user

router = APIRouter(prefix="/admin/subscriptions", tags=["Admin Subscriptions"])


def _latest_subscription(db: Session, user_id: int):
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )


def _plan_payload(plan: SubscriptionPlan | None):
    if plan is None:
        return None
    return {
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "currency": plan.currency,
        "monthly_price": plan.monthly_price,
        "annual_price": plan.annual_price,
        "max_sub_users": plan.max_sub_users,
        "max_enterprises": plan.max_enterprises,
        "max_products": plan.max_products,
        "max_clients": plan.max_clients,
        "max_invoices_per_month": plan.max_invoices_per_month,
        "features": plan.features or [],
    }


def _subscription_payload(db: Session, subscription: Subscription):
    plan = None
    if subscription.plan_code:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code == subscription.plan_code
        ).first()
    return {
        "id": subscription.id,
        "type": subscription.type,
        "billing_cycle": (
            "free"
            if subscription.plan_code == "bronze_free"
            else "annual" if subscription.type == "yearly" else subscription.type
        ),
        "plan_code": subscription.plan_code,
        "plan": _plan_payload(plan),
        "status": subscription.status,
        "start_date": subscription.start_date,
        "end_date": (
            None if subscription.plan_code == "bronze_free"
            else subscription.end_date
        ),
        "granted_by_admin": subscription.granted_by_admin,
    }


@router.post("/grant/{user_id}")
def grant_subscription(
    user_id: int,
    payload: GrantSubscriptionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    cycle = payload.resolved_cycle.value
    plan_code = payload.plan_code
    if plan_code is None:
        # Repli pour les anciennes applications mobiles.
        plan_code = "bronze_free" if cycle == "trial" else "bronze_classic"

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == plan_code,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise HTTPException(400, "Offre introuvable ou inactive")

    if cycle == "trial":
        existing_trial = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.type == "trial"
        ).first()
        if existing_trial:
            raise HTTPException(400, "Essai gratuit déjà utilisé")

    subscription = activate_subscription(
        db,
        user_id=user.id,
        plan=plan,
        billing_cycle=cycle,
        granted_by_admin=True,
    )
    db.commit()

    db.refresh(subscription)

    return {
        "message": "Abonnement mis à jour",
        "subscription": _subscription_payload(db, subscription),
    }

@router.get("/subscription/me")
def get_my_subscription(
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db)
):
    
    # ✅ SUPERADMIN : abonnement virtuel
    if current_user.is_superuser:
        return {
            "type": "superadmin",
            "billing_cycle": "unlimited",
            "plan_code": "superadmin",
            "plan": None,
            "status": "active",
            "start_date": None,
            "end_date": None,
            "granted_by_admin": True,
            "message": "Super admin has unlimited access"
        }

    subscription = _latest_subscription(db, current_user.id)

    if not subscription:
        return {
            "type": "none",
            "status": "none",
            "message": "No subscription found"
        }

    return _subscription_payload(db, subscription)

@router.get("/subscription/me-sub")
def get_parent_subscription(
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db)
):
    # Sécurité : réservé aux sub-users
    if current_user.is_main_user:
        raise HTTPException(
            status_code=403,
            detail="Route réservée aux sous-utilisateurs"
        )

    parent_user_id = current_user.parent_user_id

    if not parent_user_id:
        return {
            "status": "none",
            "type": "none"
        }

    subscription = _latest_subscription(db, parent_user_id)

    if not subscription:
        return {
            "status": "none",
            "type": "none"
        }

    return _subscription_payload(db, subscription)



@router.get("/subscriptions/all")
def get_all_subscriptions(
    _: User = Depends(require_super_user),  # seulement le superadmin
    db: Session = Depends(get_db)
):
    subscriptions = (
        db.query(Subscription)
        .join(User, User.id == Subscription.user_id)
        .add_columns(
            User.id.label("user_id"),
            User.email,
            User.username,
            Subscription.type,
            Subscription.plan_code,
            Subscription.status,
            Subscription.start_date,
            Subscription.end_date,
            Subscription.granted_by_admin,
        )
        .all()
    )

    result = []
    for s in subscriptions:
        result.append({
            "user_id": s.user_id,
            "email": s.email,
            "username": s.username,
            "type": s.type,
            "plan_code": s.plan_code,
            "status": s.status,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "granted_by_admin": s.granted_by_admin,
        })

    return {"subscriptions": result}


@router.get("/users-with-subscriptions")
def get_users_with_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user)  # seulement le superadmin
):
    # ✅ Récupère tous les utilisateurs principaux
    users = db.query(User).filter(User.is_main_user == True).all()

    result = []

    for user in users:
        # Dernier abonnement de l'utilisateur principal
        last_subscription = _latest_subscription(db, user.id)

        result.append({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "societe": user.societe_ou_entreprise,
            "avatar_url": user.avatar_url,
            "is_superuser": user.is_superuser,
            "subscription": (
                _subscription_payload(db, last_subscription)
                if last_subscription else None
            ),
            "sub_users": [
                {
                    "id": sub.id,
                    "username": sub.username,
                    "role": sub.role,
                }
                for sub in user.sub_users
            ]
        })

    return {"users": result}
