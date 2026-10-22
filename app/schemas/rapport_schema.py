from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class RapportCreate(BaseModel):
    contenu: str = Field(min_length=1, max_length=5000)
    client_reference: Optional[str] = Field(default=None, min_length=8, max_length=64)

    @field_validator("contenu")
    @classmethod
    def contenu_non_vide(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le rapport ne peut pas être vide")
        return value

class RapportUpdate(RapportCreate):
    pass

class RapportSharingUpdate(BaseModel):
    enabled: bool

class RapportSharingOut(RapportSharingUpdate):
    can_manage: bool = False


class AutomaticReportSettingsUpdate(BaseModel):
    enabled: bool
    inherit_time: bool = True
    hour: int = Field(default=18, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    detail_level: str = Field(default="detailed", pattern="^(compact|detailed)$")
    list_style: str = Field(
        default="numbered",
        pattern="^(numbered|dash|dot|bullet|arrow|check|plain)$",
    )
    include_amounts: bool = True
    include_sales: bool = True
    include_products: bool = True
    include_product_units: bool = True
    include_arrivals: bool = True
    include_interventions: bool = True
    include_consignments: bool = True
    include_payments: bool = True
    include_status_changes: bool = True
    include_maintenance: bool = True
    include_next_steps: bool = True
    publish_when_empty: bool = True


class AutomaticReportSettingsOut(AutomaticReportSettingsUpdate):
    timezone: str
    can_manage: bool = False


class RapportOut(BaseModel):
    id: int
    contenu: str
    date_creation: datetime
    date_modification: Optional[datetime] = None
    user_id: Optional[int] = None
    sub_user_id: Optional[int] = None
    auteur: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = "Main user"
    is_mine: bool = False
    is_edited: bool = False
    is_automatic: bool = False
    client_reference: Optional[str] = None

    class Config:
        from_attributes = True
