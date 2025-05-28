from datetime import datetime

from pydantic import BaseModel


class GalerieOut(BaseModel):
    id: int
    produit_id: int
    image_url: str
    date_ajout: datetime

    class Config:
        from_attributes = True
