from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    account_type: Optional[str] = "basic"
    is_main_user: bool = False
    
class RoleEnum(str, Enum):
    technicien = "technicien"
    secretaire = "secretaire"
    caissier = "caissier"
    comptable = "comptable"
    commercial = "commercial"
    gestionnaire_stock = "gestionnaire_stock"
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
    


