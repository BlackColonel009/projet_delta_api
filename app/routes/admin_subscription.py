from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models.model_souscription import Subscription, SubscriptionType
from app.models.model_user import User
from app.schemas.subscription_schema import GrantSubscriptionRequest
from app.utils.security import get_active_user, require_super_user
from app.utils.token_user import resolve_subscription_owner

router = APIRouter(prefix="/admin/subscriptions", tags=["Admin Subscriptions"])

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

    duration_map = {
        SubscriptionType.trial: 30,
        SubscriptionType.monthly: 30,
        SubscriptionType.yearly: 365,
    }

    duration = duration_map[payload.type]

    if payload.type == SubscriptionType.trial:
        existing_trial = db.query(Subscription).filter(
            Subscription.user_id == user.id,
            Subscription.type == "trial"
        ).first()
        if existing_trial:
            raise HTTPException(400, "Essai gratuit déjà utilisé")

    # Remplacer l'abonnement existant
    db.query(Subscription).filter(
        Subscription.user_id == user.id
    ).delete()

    subscription = Subscription(
        user_id=user.id,
        type=payload.type.value,
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=duration),
        granted_by_admin=True
    )

    db.add(subscription)
    db.commit()

    return {
        "message": "Subscription granted",
        "type": payload.type
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
            "status": "active",
            "start_date": None,
            "end_date": None,
            "granted_by_admin": True,
            "message": "Super admin has unlimited access"
        }

    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.end_date.desc())
        .first()
    )

    if not subscription:
        return {
            "type": "none",
            "status": "none",
            "message": "No subscription found"
        }

    return {
        "type": subscription.type,
        "status": subscription.status,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "granted_by_admin": subscription.granted_by_admin,
    }

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

    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == parent_user_id)
        .order_by(Subscription.end_date.desc())
        .first()
    )

    if not subscription:
        return {
            "status": "none",
            "type": "none"
        }

    return {
        "type": subscription.type,
        "status": subscription.status,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "granted_by_admin": subscription.granted_by_admin,
    }



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
        last_subscription = (
            db.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .order_by(Subscription.end_date.desc())
            .first()
        )

        result.append({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "societe": user.societe_ou_entreprise,
            "avatar_url": user.avatar_url,
            "is_superuser": user.is_superuser,
            "subscription": {
                "type": last_subscription.type if last_subscription else "none",
                "status": last_subscription.status if last_subscription else "none",
                "start_date": last_subscription.start_date.isoformat() if last_subscription else None,
                "end_date": last_subscription.end_date.isoformat() if last_subscription else None,
                "granted_by_admin": last_subscription.granted_by_admin if last_subscription else False
            } if last_subscription else None,
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
