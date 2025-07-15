from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TutorielCreate(BaseModel):
    titre: str
    description: Optional[str] = None
    navigation: Optional[str] = None

class TutorielOut(BaseModel):
    id: int
    titre: str
    description: Optional[str]
    navigation: Optional[str]
    image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
