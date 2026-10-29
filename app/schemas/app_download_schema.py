import re
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SUPPORTED_PLATFORMS = ("android", "windows")


class AppDownloadUpdate(BaseModel):
    enabled: bool = False
    download_url: str | None = Field(default=None, max_length=2048)
    version: str | None = Field(default=None, max_length=32)
    file_size_label: str | None = Field(default=None, max_length=40)
    sha256: str | None = Field(default=None, max_length=64)
    release_notes: str | None = Field(default=None, max_length=2000)
    published_at: datetime | None = None

    @field_validator(
        "download_url",
        "version",
        "file_size_label",
        "sha256",
        "release_notes",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("download_url")
    @classmethod
    def validate_download_url(cls, value: str | None):
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError("Le lien de téléchargement doit être une URL HTTPS valide")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str | None):
        if value is None:
            return None
        normalized = value.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("L’empreinte SHA-256 doit contenir exactement 64 caractères hexadécimaux")
        return normalized

    @model_validator(mode="after")
    def enabled_release_requires_url(self):
        if self.enabled and not self.download_url:
            raise ValueError("Un lien HTTPS est obligatoire pour activer le téléchargement")
        return self


class AppDownloadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    enabled: bool
    download_url: str | None = None
    version: str | None = None
    file_size_label: str | None = None
    sha256: str | None = None
    release_notes: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None


class AppDownloadCatalogOut(BaseModel):
    android: AppDownloadOut
    windows: AppDownloadOut
