# ✅ app/schemas/schemas_notification.py
from pydantic import BaseModel
from datetime import datetime

class NotificationCreate(BaseModel):
    titre: str
    message: str

class NotificationOut(BaseModel):
    id: int
    titre: str
    message: str
    user_id: int | None
    parent_user_id: int
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True