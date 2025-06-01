# ✅ app/routes/notification.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.models.model_notification import Notification
from app.models.model_user import SubUser
from app.schemas.notification_schema import NotificationCreate, NotificationOut
from app.utils.permissions import All_required
from app.database import get_db

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/", response_model=List[NotificationOut])
def get_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    parent_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    return db.query(Notification).filter(Notification.parent_user_id == parent_id).order_by(Notification.created_at.desc()).all()

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
        sub_user_id=SubUser.id if SubUser else None,
        sub_user_name=SubUser.username if SubUser else None,
        sub_user_role=SubUser.role if SubUser else None,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

# 🔄 Marquer une notification comme lue
@router.put("/{notif_id}/mark-as-read")
def mark_notification_as_read(
    notif_id: int,
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification non trouvée")

    notif.is_read = True
    db.commit()
    return {"message": "Notification marquée comme lue"}
