# app/config.py
from fastapi_mail import ConnectionConfig
from pydantic_settings import BaseSettings




class Settings(BaseSettings):
    PROJECT_NAME: str = "Projet DELTA"
    PROJECT_VERSION: str = "1.0.0"
    DATABASE_URL: str = "postgresql://postgres.yblmaotzdmyvynmveffd:Arnold2001DJAGBA@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"

    SUPABASE_URL: str
    SUPABASE_KEY: str


    SECRET_KEY: str = "super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""
    MAIL_FROM_NAME: str = "Trade Care"
    MAIL_ENABLED: bool = True

    # Le scheduler reste actif par défaut pour préserver le comportement en
    # production. Le fichier .env.local le désactive sur cette machine.
    SCHEDULER_ENABLED: bool = True

    # Domaine utilisé pour transformer /static/... en URL absolue dans les PDF
    # et e-mails. Il peut être surchargé sans modifier le code.
    PUBLIC_BASE_URL: str = "https://trade-care.newtechnologiestg.com"
    whatsapp_token: str
    whatsapp_phone_number_id: str
    
    DOMAIN: str = "http://localhost:8000"
    

    class Config:
        env_file = (".env", ".env.local")
        env_file_encoding = "utf-8"
    
settings = Settings()

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)
