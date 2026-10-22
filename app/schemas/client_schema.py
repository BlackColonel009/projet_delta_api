from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class ClientCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=180)
    telephone: str = Field(min_length=3, max_length=32)
    email: EmailStr | None = None
    entreprise: str | None = None
    adresse: str | None = None

    @field_validator("nom", "telephone")
    @classmethod
    def required_values_are_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ est obligatoire")
        return value

    @field_validator("email", "entreprise", "adresse", mode="before")
    @classmethod
    def normalize_optional_values(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ClientOut(BaseModel):
    id: int
    nom: str
    telephone: str | None = None
    email: str | None = None
    entreprise: str | None = None
    adresse: str | None = None

    class Config:
        from_attributes = True


class ClientWelcomeEmailRequest(BaseModel):
    language: Literal["fr", "en"] = "fr"
