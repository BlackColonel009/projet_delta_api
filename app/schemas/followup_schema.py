from pydantic import BaseModel, conint


class UpdateDelaiRelanceSchema(BaseModel):
    delai_avant_relance: conint(ge=1, le=90)


class PaymentReminderSettingsUpdate(BaseModel):
    enabled: bool = True
    start_after_days: conint(ge=1, le=90) = 2


class ClientFollowupSettingsUpdate(BaseModel):
    enabled: bool = True
    thank_you_delay_days: conint(ge=0, le=90) = 1
    recommendations_enabled: bool = True
    first_recommendation_delay_days: conint(ge=1, le=180) = 10
    recommendation_interval_days: conint(ge=1, le=180) = 14
