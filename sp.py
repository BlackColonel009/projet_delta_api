# # sp.py

# from app.database import SessionLocal
# from app.models.model_user import User
# from app.utils.security import hash_password

# def create_superuser():
#     db = SessionLocal()

#     try:
#         existing = db.query(User).filter(User.email == "admin@delta.com").first()
#         if existing:
#             print("🔁 SuperUser already exists")
#         else:
#             super_user = User(
#                 email="admin@delta.com",
#                 password_hash=hash_password("admin123"),
#                 is_main_user=True,
#                 is_superuser=True,
#                 username="admin"
#             )
#             db.add(super_user)
#             db.commit()
#             print("✅ SuperUser created with email: admin@delta.com and password: admin123")
#     except Exception as e:
#         print(f"❌ Error creating superuser: {e}")
#     finally:
#         db.close()

# if __name__ == "__main__":
#     create_superuser()

# SHOW search_path;
# INSERT INTO users (
#     email,
#     password_hash,
#     is_main_user,
#     is_superuser,
#     avatar_url,
#     bio,
#     username,
#     societe_ou_entreprise,
#     account_type,
#     created_at,
#     devise,
#     telephone,
#     logo_entreprise,
#     addresse
# ) VALUES (
#     'admin@delta.com',
#     '$2b$12$Dni6KN.WgoYkAeLQwWyv..6pEPyJeuPgCCZ1gQEBGoKhHcuwAwfNO', -- hash de 'admin123' avec bcrypt
#     true,
#     true,
#     NULL,
#     NULL,
#     'Admin',
#     'Trade Care',
#     'basic',
#     NOW(),
#     '€',
#     NULL,
#     NULL,
#     NULL
# );
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("admin123"))
