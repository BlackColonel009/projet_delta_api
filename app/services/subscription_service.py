from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.model_souscription import Subscription
from app.models.model_subscription_plan import SubscriptionPlan


def subscription_duration_days(cycle: str) -> int:
    return 365 if cycle in {"annual", "yearly"} else 30


def legacy_subscription_type(cycle: str) -> str:
    return "yearly" if cycle == "annual" else cycle


def create_trial_subscription(db: Session, user_id: int):
    subscription = Subscription(
        user_id=user_id,
        plan_code="bronze_free",
        type="trial",
        status="active",
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        granted_by_admin=False
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def activate_subscription(
    db: Session,
    *,
    user_id: int,
    plan: SubscriptionPlan,
    billing_cycle: str,
    granted_by_admin: bool = True,
) -> Subscription:
    """Remplace l'abonnement actif tout en conservant l'historique."""
    db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == "active",
    ).update({Subscription.status: "replaced"}, synchronize_session=False)

    now = datetime.utcnow()
    subscription = Subscription(
        user_id=user_id,
        plan_code=plan.code,
        type=legacy_subscription_type(billing_cycle),
        status="active",
        start_date=now,
        end_date=now + timedelta(days=subscription_duration_days(billing_cycle)),
        granted_by_admin=granted_by_admin,
    )
    db.add(subscription)
    db.flush()
    return subscription
