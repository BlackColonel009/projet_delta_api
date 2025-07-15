from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    account_type: Optional[str] = "basic"
    is_main_user: bool = False
    societe_ou_entreprise: Optional[str] = None  # ✅
    devise: Optional[str] = "€"
    
class RoleEnum(str, Enum):
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
    
class MainUserData(BaseModel):
    societe_ou_entreprise: Optional[str]
    logo_entreprise: Optional[str]
    devise: Optional[str]

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GroupUserLogin(BaseModel):
    parent_email: EmailStr
    username: str
    password: str
    
class SubUserOut(BaseModel):
    id: int
    username: str
    bio: Optional[str]
    avatar_url: Optional[str]
    role: Optional[str]
    main_user_data: Optional[MainUserData]

