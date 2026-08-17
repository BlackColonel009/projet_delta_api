from fastapi import Depends, HTTPException
from datetime import datetime
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_souscription import Subscription
from app.utils.security import get_active_user, get_current_user

from app.models.model_user import User


def require_active_subscription(
    current_user: User = Depends(get_active_user),
    db: Session = Depends(get_db)
):
    print(f"🔹 Checking subscription for user: {getattr(current_user, 'email', getattr(current_user, 'username', 'UNKNOWN'))}, id={current_user.id}")
    print(f"   is_main_user: {current_user.is_main_user}, is_superuser: {getattr(current_user, 'is_superuser', False)}")

    # ✅ Superadmin : accès total
    if getattr(current_user, "is_superuser", False):
        print("✅ Superadmin detected, skipping subscription check")
        return current_user

    # ✅ Déterminer le propriétaire réel de l'abonnement
    subscription_owner_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    # 🔹 Vérifier si le parent est superadmin
    parent_user = db.query(User).filter(User.id == subscription_owner_id).first()
    if parent_user and parent_user.is_superuser:
        print("✅ Parent is superadmin, access granted")
        return current_user

    print(f"   Subscription owner id: {subscription_owner_id}")

    # ✅ Récupérer l'abonnement le plus récent
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == subscription_owner_id)
        .order_by(Subscription.end_date.desc())
        .first()
    )

    print(f"   Retrieved subscription: {sub}")

    # ❌ Aucun abonnement
    if not sub or sub.type == "none":
        print("❌ No subscription found, blocking access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="NO_SUBSCRIPTION"
        )

    # ❌ Statut invalide
    if sub.status != "active":
        print("❌ Subscription status invalid, blocking access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUBSCRIPTION_EXPIRED"
        )

    # ❌ Expiration réelle
    if sub.end_date < datetime.utcnow():
        sub.status = "expired"
        db.commit()
        print("❌ Subscription expired, blocking access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUBSCRIPTION_EXPIRED"
        )

    print("✅ Subscription valid, access granted")
    return current_user
