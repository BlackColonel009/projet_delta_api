# 🔐 UTILITAIRES DE SÉCURITÉ POUR AUTHENTIFICATION ET CONTRÔLE D'ACCÈS
# Fichier : app/utils/security.py

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_user import User
from app.models.model_user import SubUser
from app.config import settings
from app.models.model_role import Role, Permission

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# 🔒 Hasher un mot de passe
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# 🔐 Vérifier un mot de passe contre un hash
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# 🔐 Générer un token JWT
def create_access_token(data: dict, expires_delta: int = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# ✅ Récupérer l'utilisateur principal depuis le token JWT
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception
    


# ✅ Récupérer un sous-utilisateur à partir d’un token groupé : parent_email:username
async def get_current_sub_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> SubUser:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate sub-user")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub_id: str = payload.get("sub")
        if not sub_id or ":" not in sub_id:
            raise credentials_exception
        parent_email, username = sub_id.split(":")
        parent = db.query(User).filter(User.email == parent_email).first()
        if not parent:
            raise credentials_exception
        sub_user = db.query(SubUser).filter(SubUser.username == username, SubUser.parent_user_id == parent.id).first()
        if not sub_user:
            raise credentials_exception
        return sub_user
    except JWTError:
        raise credentials_exception


# 🔐 Vérifie si un utilisateur est super admin
async def require_super_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You are not a super admin")
    return current_user

# 🔐 Vérifie le rôle du sub-user (à intégrer plus tard selon besoin d'accès par rôle)
def require_role(required_role: str):
    def role_checker(token: str = Depends(oauth2_scheme)):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            token_role = payload.get("role")
            if not token_role or token_role != required_role:
                raise HTTPException(status_code=403, detail="Access denied: insufficient role")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    return role_checker

# 🔐 Vérifie si le rôle fait partie d’un ensemble autorisé (pour autorisations multiples)
def require_any_role(allowed_roles: list[str]):
    def role_checker(token: str = Depends(oauth2_scheme)):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            token_role = payload.get("role")
            if token_role not in allowed_roles:
                raise HTTPException(status_code=403, detail=f"Access denied: requires one of roles {allowed_roles}")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    return role_checker



# Vérifie si le rôle courant a la permission attendue
def check_permission(required_permission: str):
    def permission_checker(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
    ):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            role = payload.get("role")
            if not role:
                raise HTTPException(status_code=403, detail="Aucun rôle détecté dans le token")

            role_obj = db.query(Role).filter(Role.name == role).first()
            if not role_obj:
                raise HTTPException(status_code=403, detail="Rôle non reconnu")

            if required_permission not in [p.name for p in role_obj.permissions]:
                raise HTTPException(status_code=403, detail=f"Permission '{required_permission}' refusée")

        except JWTError:
            raise HTTPException(status_code=401, detail="Token invalide")
    return permission_checker

#Accès réservé à l'utilisateur principal qui a is_main_user = true

def require_main_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_main_user:
        raise HTTPException(status_code=403, detail="Accès réservé à l'utilisateur Manager d'Equipe")
    return current_user