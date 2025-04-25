from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Connexion à PostgreSQL
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base ORM
Base = declarative_base()

# Dépendance à injecter dans FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
