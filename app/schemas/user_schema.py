from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    account_type: Optional[str] = "basic"
    is_main_user: bool = False
    societe_ou_entreprise: Optional[str] = None  # ✅
    
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
    password: str
    role: RoleEnum

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GroupUserLogin(BaseModel):
    parent_email: EmailStr
    username: str
    password: str
    


