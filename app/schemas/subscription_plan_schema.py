from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubscriptionFeature(str, Enum):
    sales_purchases = "sales_purchases"
    basic_invoice = "basic_invoice"
    professional_invoice = "professional_invoice"
    advanced_exports = "advanced_exports"
    basic_qr = "basic_qr"
    full_qr = "full_qr"
    in_app_stock_alerts = "in_app_stock_alerts"
    stock_alerts = "stock_alerts"
    financial_dashboard = "financial_dashboard"
    annual_comparison = "annual_comparison"
    reports = "reports"
    theme_colors = "theme_colors"
    custom_theme = "custom_theme"
    client_followup = "client_followup"
    product_recommendation = "product_recommendation"
    interventions = "interventions"
    depots = "depots"
    multi_depot = "multi_depot"
    priority_support = "priority_support"
    onboarding = "onboarding"
    multi_enterprise = "multi_enterprise"
    group_dashboard = "group_dashboard"
    global_stock_search = "global_stock_search"


class SubscriptionPlanUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    monthly_price: float = Field(ge=0)
    annual_price: float = Field(ge=0)
    currency: str = Field(min_length=2, max_length=10)
    max_sub_users: int | None = Field(default=None, ge=0)
    max_enterprises: int | None = Field(default=None, ge=1)
    max_products: int | None = Field(default=None, ge=0)
    max_clients: int | None = Field(default=None, ge=0)
    max_invoices_per_month: int | None = Field(default=None, ge=0)
    max_invoice_shares_per_month: int | None = Field(default=None, ge=0)
    features: list[SubscriptionFeature] = Field(default_factory=list)
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("features")
    @classmethod
    def unique_features(
        cls,
        value: list[SubscriptionFeature],
    ) -> list[SubscriptionFeature]:
        return list(dict.fromkeys(value))


class SubscriptionPlanOut(SubscriptionPlanUpdate):
    model_config = ConfigDict(from_attributes=True)

    code: str
    updated_at: datetime
