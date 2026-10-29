from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTACT_ICON_KEYS = (
    "email",
    "phone",
    "whatsapp",
    "facebook",
    "linkedin",
    "telegram",
    "instagram",
    "youtube",
    "tiktok",
    "x",
    "website",
    "other",
)


class PlatformContactLinkPayload(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    icon_key: str = Field(default="other", max_length=24)
    url: str = Field(min_length=3, max_length=2048)
    is_visible: bool = True
    sort_order: int = Field(default=0, ge=0, le=9999)

    @field_validator("label", "icon_key", "url", mode="before")
    @classmethod
    def strip_text(cls, value):
        return str(value or "").strip()

    @field_validator("icon_key")
    @classmethod
    def validate_icon_key(cls, value: str):
        value = value.lower()
        if value not in CONTACT_ICON_KEYS:
            raise ValueError("Type de contact non pris en charge")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str):
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        if scheme == "https" and parsed.netloc:
            return value
        if scheme == "mailto" and parsed.path and "@" in parsed.path:
            return value
        if scheme == "tel" and parsed.path:
            return value
        raise ValueError("Utilisez un lien HTTPS, mailto: ou tel: valide")


class PlatformContactLinkOut(PlatformContactLinkPayload):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
