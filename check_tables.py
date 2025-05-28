from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

try:
    with engine.connect() as conn:
        print("✅ Connexion réussie")
except Exception as e:
        print("❌ Erreur :", e)
