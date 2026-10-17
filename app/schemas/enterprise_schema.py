from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ServiceCode = Literal["gestion_principale", "consigne"]
EnterpriseType = Literal["standard", "consigne"]


class EnterpriseServiceCreate(BaseModel):
    service_code: ServiceCode
    enabled: bool = True
    configuration_json: dict[str, Any] = Field(default_factory=dict)


class EnterpriseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=80)
    enterprise_type: EnterpriseType | None = None
    # Compatibilite temporaire avec les premiers clients de l'API. Le type
    # d'entreprise est desormais le choix fonctionnel officiel.
    service_codes: list[ServiceCode] | None = None
    address: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="Africa/Lome", max_length=64)

    @field_validator("service_codes")
    @classmethod
    def validate_services(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(value))
        if not normalized:
            raise ValueError("Choisissez un type d'entreprise")
        if set(normalized) not in ({"gestion_principale"}, {"consigne"}):
            raise ValueError(
                "Une entreprise liee doit etre standard ou consigne, pas hybride"
            )
        return normalized


class EnterpriseSelection(BaseModel):
    enterprise_id: int = Field(gt=0)


class EnterpriseServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_code: str
    enabled: bool
    configuration_json: dict[str, Any]


class EnterpriseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    code: str
    is_primary: bool
    enterprise_type: str
    status: str
    address: str | None
    phone: str | None
    email: str | None
    logo_url: str | None
    app_theme: str
    theme_mode: str
    invoice_color: str
    simple_invoice_template: str
    professional_invoice_template: str
    currency: str
    timezone: str
    map_position_x: float | None
    map_position_y: float | None
    map_order: int
    created_at: datetime
    service_profiles: list[EnterpriseServiceOut]


class EnterpriseContextOut(BaseModel):
    group_id: int
    group_name: str
    owner_user_id: int
    role: str
    scope: str
    can_switch_enterprise: bool
    assigned_enterprise_id: int | None
    default_enterprise_id: int
    enterprises: list[EnterpriseOut]
