# app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Projet DELTA"
    PROJECT_VERSION: str = "1.0.0"
    DATABASE_URL: str = "postgresql://postgres:roland2001@localhost:5433/trade_care?client_encoding=UTF8"
    SECRET_KEY: str = "super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
