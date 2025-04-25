# create_superuser.py

from app.database import SessionLocal
from app.models.model_user import User
from app.utils.security import hash_password

db = SessionLocal()

# Vérifie s’il existe déjà
existing = db.query(User).filter(User.email == "admin@delta.com").first()
if existing:
    print("SuperUser already exists")
else:
    super_user = User(
        email="admin@delta.com",
        password_hash=hash_password("admin123"),
        is_main_user=True,
        is_superuser=True
    )
    db.add(super_user)
    db.commit()
    print("✅ SuperUser created with email: admin@delta.com and password: admin123")
