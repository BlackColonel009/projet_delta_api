from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import datetime

class DepotServiceCreate(BaseModel):
    nom: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    mode_tarification: str  # "duree" ou "unitaire"

    @field_validator("mode_tarification")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        from app.services.depot_pricing_service import normalize_pricing_mode

        return normalize_pricing_mode(value)

class DepotServiceOut(BaseModel):
    id: int
    nom: str
    description: Optional[str]
    mode_tarification: str
    date_creation: datetime

    model_config = ConfigDict(from_attributes=True)
