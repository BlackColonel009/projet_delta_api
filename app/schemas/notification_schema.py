# ✅ app/schemas/schemas_notification.py
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime


_IMAGE_PATH_PATTERNS = (
    re.compile(
        r"(?:image_url|image_path|imagePath|chemin_image|path)\s*[:=]\s*['\"]?[^,}\]\n]+['\"]?,?",
        re.IGNORECASE,
    ),
    re.compile(
        r"https?://\S+\.(?:png|jpe?g|gif|webp)(?:\?\S*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:/static/|/uploads?/|\\uploads?\\)\S+\.(?:png|jpe?g|gif|webp)",
        re.IGNORECASE,
    ),
)


def sanitize_notification_text(value: str) -> str:
    cleaned = value.strip()
    for pattern in _IMAGE_PATH_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()

class NotificationCreate(BaseModel):
    titre: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("titre", "message")
    @classmethod
    def clean_content(cls, value: str) -> str:
        cleaned = sanitize_notification_text(value)
        if not cleaned:
            raise ValueError("Le contenu de la notification ne peut pas être vide")
        return cleaned

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titre: str
    message: str
    user_id: int | None
    parent_user_id: int
    sub_user_id: int | None = None
    sub_user_name: str | None = None
    sub_user_role: str | None = None
    is_read: bool
    created_at: datetime


class CompanyReminderUpdate(BaseModel):
    enabled: bool
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)


class CompanyReminderOut(CompanyReminderUpdate):
    revision: int
    updated_at: datetime | None = None
