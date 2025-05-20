from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RapportCreate(BaseModel):
    # id: int
    contenu: str
    # date_creation: datetime
    # auteur: Optional[str] = None

class RapportOut(BaseModel):
    id: int
    contenu: str
    date_creation: datetime
    user_id: Optional[int] = None
    sub_user_id: Optional[int] = None
    auteur: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = "Main user"

    class Config:
        from_attributes = True
