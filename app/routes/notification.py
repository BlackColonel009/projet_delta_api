# ✅ app/routes/notification.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.models.model_notification import Notification
from app.models.model_user import User
from app.schemas.notification_schema import (
    CompanyReminderOut,
    CompanyReminderUpdate,
    NotificationCreate,
    NotificationOut,
)
from app.utils.permissions import All_required
from app.database import get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _company_owner(db: Session, current_user) -> User:
    if current_user.is_main_user:
        return current_user
    owner = db.query(User).filter(User.id == current_user.parent_user_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    return owner


def _can_manage_company_settings(current_user) -> bool:
    if current_user.is_main_user:
        return True
    return str(getattr(current_user, "role", "")).strip().lower() == "admin"


def _reminder_payload(owner: User) -> dict:
    return {
        "enabled": bool(owner.daily_report_reminder_enabled),
        "hour": owner.daily_report_reminder_hour,
        "minute": owner.daily_report_reminder_minute,
        "revision": owner.daily_report_reminder_revision,
        "updated_at": owner.daily_report_reminder_updated_at,
    }

@router.get("/", response_model=List[NotificationOut])
def get_notifications(
    unread_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    max_age_days: int | None = None,
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    # Les alertes système sont réservées au compte principal. L'historique
    # complet reste toutefois consultable par les membres de l'entreprise.
    if unread_only and not current_user.is_main_user:
        return []

    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    parent_id = (
        current_user.id
        if current_user.is_main_user
        else current_user.parent_user_id
    )
    query = db.query(Notification).filter(
        Notification.parent_user_id == parent_id
    )
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    if max_age_days is not None:
        safe_days = max(1, min(max_age_days, 30))
        query = query.filter(
            Notification.created_at >= datetime.utcnow() - timedelta(days=safe_days)
        )

    return (
        query.order_by(
            Notification.created_at.asc()
            if unread_only
            else Notification.created_at.desc()
        )
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )

@router.post("/", response_model=NotificationOut)
def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    parent_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    notif = Notification(
        titre=data.titre,
        message=data.message,
        parent_user_id=parent_id,
        user_id=None if current_user.is_main_user else current_user.id,
        sub_user_id=current_user.id if not current_user.is_main_user else None,
        sub_user_name=current_user.username if not current_user.is_main_user else None,
        sub_user_role=current_user.role if not current_user.is_main_user else None,
        # Une action du compte principal est déjà confirmée localement. On la
        # conserve pour l'historique sans la lui renvoyer au prochain polling.
        is_read=current_user.is_main_user,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


@router.get("/daily-reminder", response_model=CompanyReminderOut)
def get_company_daily_reminder(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    """Réglage commun lu par chaque appareil de la même entreprise."""
    return _reminder_payload(_company_owner(db, current_user))


@router.put("/daily-reminder", response_model=CompanyReminderOut)
def update_company_daily_reminder(
    data: CompanyReminderUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    if not _can_manage_company_settings(current_user):
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent modifier les paramètres.",
        )

    owner = _company_owner(db, current_user)
    owner.daily_report_reminder_enabled = data.enabled
    owner.daily_report_reminder_hour = data.hour
    owner.daily_report_reminder_minute = data.minute
    owner.daily_report_reminder_revision = (
        owner.daily_report_reminder_revision or 0
    ) + 1
    owner.daily_report_reminder_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(owner)
    return _reminder_payload(owner)

# 🔄 Marquer une notification comme lue
@router.put("/{notif_id}/mark-as-read")
def mark_notification_as_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(All_required()),
):
    if not current_user.is_main_user:
        raise HTTPException(
            status_code=403,
            detail="Seul le compte principal peut gérer les notifications.",
        )

    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.parent_user_id == current_user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification non trouvée")

    notif.is_read = True
    db.commit()
    return {"message": "Notification marquée comme lue"}
