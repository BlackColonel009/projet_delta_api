from pydantic import BaseModel, EmailStr, field_validator
from typing import Literal, Optional
from enum import Enum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    account_type: Optional[str] = "bronze_free"
    is_main_user: bool = True
    societe_ou_entreprise: Optional[str] = None  # ✅
    devise: Optional[str] = "€"
    interface_language: Literal["fr", "en"] = "fr"
    
class RoleEnum(str, Enum):
    directeur = "Directeur"
    technicien = "Technicien(ne)"
    secretaire = "Secretaire"
    caissier = "Caissier(e)"
    comptable = "Comptable"
    commercial = "Commerciale"
    gestionnaire_stock = "Gestionnaire de stock"
    admin = "admin"
    
class SubUserCreate(BaseModel):
    parent_email: EmailStr
    username: str
    bio: str | None
    password: str
    role: RoleEnum
    # Facultatif pour conserver la compatibilite avec les anciens mobiles.
    # Sans valeur, le collaborateur est affecte a l'entreprise principale.
    enterprise_id: int | None = None
    
class MainUserData(BaseModel):
    societe_ou_entreprise: Optional[str]
    logo_entreprise: Optional[str]
    devise: Optional[str]
    tva: Optional[float]
    nif: Optional[str]
    addresse: Optional[str]
    facture_color: Optional[str] 
    app_theme: Optional[str] = "tradecare"
    theme_mode: Optional[str] = "system"


class CompanyInvoiceThemeUpdate(BaseModel):
    facture_color: str
    # Optionnels pour conserver la compatibilité avec les anciennes versions
    # mobiles qui n'envoyaient que la couleur.
    simple_invoice_template: Optional[str] = None
    professional_invoice_template: Optional[str] = None
    show_invoice_agent: Optional[bool] = None


class CompanyThemeUpdate(BaseModel):
    app_theme: Literal[
        "tradecare",
        "ocean",
        "emerald",
        "sunset",
        "ruby",
        "midnight",
    ]
    theme_mode: Literal["system", "light", "dark"]


class InterfaceLanguageUpdate(BaseModel):
    language: Literal["fr", "en"]


class SessionLockUpdate(BaseModel):
    session_lock_minutes: int
    password: Optional[str] = None

    @field_validator("session_lock_minutes")
    @classmethod
    def validate_delay(cls, value: int) -> int:
        if value not in {0, 5, 15, 30, 60}:
            raise ValueError("Délai de verrouillage invalide")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if len(value) < 5:
            raise ValueError(
                "Le mot de passe de verrouillage doit contenir au moins 5 caractères"
            )
        return value


class SessionUnlockRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 5:
            raise ValueError("Mot de passe de verrouillage invalide")
        return value


class DeleteAccountRequest(BaseModel):
    password: str
    confirmation: Literal["SUPPRIMER MON COMPTE"]

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GroupUserLogin(BaseModel):
    parent_email: EmailStr
    username: str
    password: str
    
class SubUserOut(BaseModel):
    id: int
    is_main_user: bool = False
    username: str
    bio: Optional[str]
    avatar_url: Optional[str]
    role: Optional[str]
    main_user_data: Optional[MainUserData]
    session_lock_minutes: int = 0
    session_lock_configured: bool = False
    interface_language: Literal["fr", "en"] = "fr"

