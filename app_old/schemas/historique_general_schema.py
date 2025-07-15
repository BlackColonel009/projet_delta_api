from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
# 🧾 Schéma

class MiniSubUser(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        from_attributes = True
        
class UserMiniOut(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

class HistoriqueCreate(BaseModel):
    action: str
    type_entite: str
    entite_id: Optional[int] = None
    user_id: Optional[int] = None
    details: Optional[str] = None

class HistoriqueOut(HistoriqueCreate):
    id: int
    date_action: datetime
    user: UserMiniOut
    sub_user: Optional[MiniSubUser] = None
    nom_user: Optional[str]  # ✅ nouveau
    nom_sub_user: Optional[str]  # ✅ nouveau

    class Config:
        from_attributes = True
        
