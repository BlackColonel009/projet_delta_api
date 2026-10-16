from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime

class DepotTarifCreate(BaseModel):
    service_id: int
    nom_tarif: str = Field(min_length=2, max_length=120)
    mode_tarification: str  # "duree" ou "unitaire"
    tarif_unitaire: Optional[float] = Field(default=None, ge=0)
    tarif_par_minute: Optional[float] = Field(default=None, ge=0)
    actif: Optional[bool] = True

    @field_validator("mode_tarification")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        from app.services.depot_pricing_service import normalize_pricing_mode

        return normalize_pricing_mode(value)

    @model_validator(mode="after")
    def validate_price(self):
        if self.mode_tarification == "unitaire" and self.tarif_unitaire is None:
            raise ValueError("Le tarif unitaire est obligatoire.")
        if self.mode_tarification == "duree" and self.tarif_par_minute is None:
            raise ValueError("Le tarif par minute est obligatoire.")
        return self

    

class DepotTarifOut(BaseModel):
    id: int
    nom_tarif: str
    mode_tarification: str
    tarif_unitaire: Optional[float]
    tarif_par_minute: Optional[float]
    service_id: int
    actif: bool
    date_creation: datetime
    service_nom: str


    model_config = ConfigDict(from_attributes=True)
