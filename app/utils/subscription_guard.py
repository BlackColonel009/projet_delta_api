from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_souscription import Subscription
from app.models.model_subscription_plan import SubscriptionPlan
from app.models.model_user import User
from app.utils.security import get_active_user


FEATURE_IMPLICATIONS = {
    "professional_invoice": {"basic_invoice"},
    "full_qr": {"basic_qr"},
    "stock_alerts": {"in_app_stock_alerts"},
    "custom_theme": {"theme_colors"},
    "multi_depot": {"depots"},
}


@dataclass(frozen=True)
class SubscriptionAccess:
    owner_id: int
    plan_code: str
    plan_name: str
    features: frozenset[str]
    max_sub_users: int | None
    max_products: int | None
    max_clients: int | None
    max_invoices_per_month: int | None
    unlimited: bool = False

    def has_feature(self, feature: str) -> bool:
        if self.unlimited or feature in self.features:
            return True
        return any(
            owned_feature in self.features
            and feature in implied_features
            for owned_feature, implied_features in FEATURE_IMPLICATIONS.items()
        )

    def quota(self, field: str) -> int | None:
        return None if self.unlimited else getattr(self, field)

    def effective_features(self) -> frozenset[str]:
        if self.unlimited:
            return frozenset({"*"})
        values = set(self.features)
        for owned_feature, implied_features in FEATURE_IMPLICATIONS.items():
            if owned_feature in self.features:
                values.update(implied_features)
        return frozenset(values)


def subscription_owner_id(current_user) -> int:
    if getattr(current_user, "is_main_user", False):
        return current_user.id
    return current_user.parent_user_id


def _error(code: str, message: str, **context):
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message, **context},
    )


def subscription_is_expired(
    plan_code: str,
    end_date: datetime,
    now: datetime | None = None,
) -> bool:
    if plan_code == "bronze_free":
        return False
    return end_date < (now or datetime.utcnow())


def resolve_subscription_access(
    db: Session,
    current_user,
) -> SubscriptionAccess:
    owner_id = subscription_owner_id(current_user)
    if owner_id is None:
        raise _error(
            "NO_SUBSCRIPTION_OWNER",
            "Cette session n’est rattachée à aucune entreprise.",
        )

    if getattr(current_user, "is_superuser", False):
        return SubscriptionAccess(
            owner_id=owner_id,
            plan_code="superadmin",
            plan_name="Super administrateur",
            features=frozenset(),
            max_sub_users=None,
            max_products=None,
            max_clients=None,
            max_invoices_per_month=None,
            unlimited=True,
        )

    owner = db.query(User).filter(User.id == owner_id).first()
    if owner and owner.is_superuser:
        return SubscriptionAccess(
            owner_id=owner_id,
            plan_code="superadmin",
            plan_name="Super administrateur",
            features=frozenset(),
            max_sub_users=None,
            max_products=None,
            max_clients=None,
            max_invoices_per_month=None,
            unlimited=True,
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == owner_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .first()
    )
    if not subscription or subscription.type == "none":
        raise _error(
            "NO_SUBSCRIPTION",
            "Aucun abonnement actif n’est associé à cette entreprise.",
        )

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == subscription.plan_code,
        SubscriptionPlan.is_active.is_(True),
    ).first()
    if not plan:
        raise _error(
            "SUBSCRIPTION_PLAN_UNAVAILABLE",
            "L’offre associée à cette entreprise est indisponible.",
            plan_code=subscription.plan_code,
        )

    if subscription.status != "active":
        raise _error(
            "SUBSCRIPTION_EXPIRED",
            "L’abonnement de cette entreprise n’est plus actif.",
        )

    # Bronze Gratuit est un palier permanent. Sa date historique reste en base
    # pour compatibilité, mais elle ne provoque pas d'expiration.
    if subscription_is_expired(plan.code, subscription.end_date):
        subscription.status = "expired"
        db.commit()
        raise _error(
            "SUBSCRIPTION_EXPIRED",
            "L’abonnement de cette entreprise a expiré.",
        )

    return SubscriptionAccess(
        owner_id=owner_id,
        plan_code=plan.code,
        plan_name=plan.name,
        features=frozenset(plan.features or []),
        max_sub_users=plan.max_sub_users,
        max_products=plan.max_products,
        max_clients=plan.max_clients,
        max_invoices_per_month=plan.max_invoices_per_month,
    )


def require_active_subscription(
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    resolve_subscription_access(db, current_user)
    return current_user


def require_subscription_feature(feature: str):
    def feature_checker(
        current_user=Depends(get_active_user),
        db: Session = Depends(get_db),
    ):
        access = resolve_subscription_access(db, current_user)
        if not access.has_feature(feature):
            raise _error(
                "FEATURE_NOT_INCLUDED",
                "Cette fonctionnalité nécessite une offre supérieure.",
                feature=feature,
                plan_code=access.plan_code,
                plan_name=access.plan_name,
            )
        return access

    return feature_checker


def enforce_feature_access(
    db: Session,
    current_user,
    feature: str,
) -> SubscriptionAccess:
    access = resolve_subscription_access(db, current_user)
    if not access.has_feature(feature):
        raise _error(
            "FEATURE_NOT_INCLUDED",
            "Cette fonctionnalité nécessite une offre supérieure.",
            feature=feature,
            plan_code=access.plan_code,
            plan_name=access.plan_name,
        )
    return access


def enforce_quota_limit(
    access: SubscriptionAccess,
    quota_field: str,
    current_usage: int,
    resource_label: str,
) -> None:
    limit = access.quota(quota_field)
    if limit is not None and current_usage >= limit:
        raise _error(
            "QUOTA_REACHED",
            f"La limite de {resource_label} de votre offre est atteinte.",
            resource=quota_field,
            current=current_usage,
            limit=limit,
            plan_code=access.plan_code,
            plan_name=access.plan_name,
        )


def enforce_subscription_quota(
    db: Session,
    current_user,
    quota_field: str,
    current_usage: int,
    resource_label: str,
) -> None:
    access = resolve_subscription_access(db, current_user)
    enforce_quota_limit(access, quota_field, current_usage, resource_label)


def enforce_invoice_quota(db: Session, current_user) -> None:
    # Imports locaux pour ne pas créer de cycle entre modèles et sécurité.
    from app.models.model_facture import Facture
    from app.models.model_facture_depot import FactureDepot

    access = resolve_subscription_access(db, current_user)
    start = datetime.utcnow().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    standard_count = db.query(Facture).filter(
        Facture.user_id == access.owner_id,
        Facture.date_creation >= start,
        Facture.date_creation < end,
    ).count()
    depot_count = db.query(FactureDepot).filter(
        FactureDepot.user_id == access.owner_id,
        FactureDepot.date_facture >= start,
        FactureDepot.date_facture < end,
    ).count()
    enforce_quota_limit(
        access,
        "max_invoices_per_month",
        standard_count + depot_count,
        "factures mensuelles",
    )


def company_has_feature(db: Session, owner_id: int, feature: str) -> bool:
    owner = db.query(User).filter(User.id == owner_id).first()
    if not owner:
        return False
    try:
        return resolve_subscription_access(db, owner).has_feature(feature)
    except HTTPException:
        return False
