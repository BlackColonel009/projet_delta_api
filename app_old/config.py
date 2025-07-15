# app/config.py
from fastapi_mail import ConnectionConfig
from pydantic import computed_field
from pydantic_settings import BaseSettings

conf = ConnectionConfig(
    MAIL_USERNAME="imlogang009@gmail.com",
    MAIL_PASSWORD="voexesyjnnljrauk",
    MAIL_FROM="imlogang009@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="TRADE CARE",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)


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
    
    DOMAIN: str = "http://localhost:8000"
    

    class Config:
        env_file = ".env"
    
settings = Settings()

