from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class RapportCreate(BaseModel):
    contenu: str = Field(min_length=1, max_length=5000)

    @field_validator("contenu")
    @classmethod
    def contenu_non_vide(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le rapport ne peut pas être vide")
        return value

class RapportOut(BaseModel):
    id: int
    contenu: str
    date_creation: datetime
    user_id: Optional[int] = None
    sub_user_id: Optional[int] = None
    auteur: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = "Main user"
    is_mine: bool = False

    class Config:
        from_attributes = True
