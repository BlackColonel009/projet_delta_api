from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class FournisseurCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=180)
    telephone: str = Field(min_length=3, max_length=32)
    email: EmailStr | None = None
    adresse: str | None = None
    type_fourniture: str | None = None

    @field_validator("nom", "telephone")
    @classmethod
    def required_values_are_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ est obligatoire")
        return value

    @field_validator("email", "adresse", "type_fourniture", mode="before")
    @classmethod
    def normalize_optional_values(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class FournisseurOut(BaseModel):
    id: int
    nom: str
    email: str | None = None
    telephone: str | None = None
    adresse: str | None = None
    type_fourniture: str | None = None
    date_creation: datetime

    class Config:
        from_attributes = True
