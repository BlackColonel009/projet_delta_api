# 🔐 ROUTES AVANCÉES AUTHENTIFICATION
# Fichier : app/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from app.schemas.user_schema import UserCreate, SubUserCreate, UserLogin, GroupUserLogin
from app.models.model_user import User, SubUser
from app.models.model_role import Role
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_sub_user, require_role, 
    require_super_user, require_any_role, require_main_user
)
from app.database import get_db

router = APIRouter()

# 🔒 Route pour créer un utilisateur principal (Single user)
@router.post("/register", tags=["Authentification"])
def register_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        is_main_user=data.is_main_user,
        is_superuser=False,# par défaut
        account_type=data.account_type,
        societe_ou_entreprise=data.societe_ou_entreprise  
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}

# 🔒 Route pour créer un sous-utilisateur sous un utilisateur principal
@router.post("/register_sub", tags=["Authentification"])
def register_sub_user(
    data: SubUserCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_user)  # ✅ protection ici
):
    parent = db.query(User).filter(User.email == data.parent_email).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent user not found")
    
    # ✅ Vérifie que le rôle demandé est défini dans la table roles
    if not db.query(Role).filter(Role.name == data.role).first():
        raise HTTPException(status_code=400, detail="Rôle non autorisé")
    
    if not current_user.is_main_user:
        raise HTTPException(
            status_code=403,
            detail="Seuls les utilisateurs gestionnaire ou leader peuvent créer des subusers."
        )
    
    new_sub = SubUser(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        parent_user_id=parent.id
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return {"message": "Sub-user created successfully"}


# 🔑 Connexion utilisateur principal (Single User)
@router.post("/login", tags=["Authentification"])
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    🔐 Login route compatible avec OAuth2PasswordRequestForm (Swagger /docs + applis)
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    access_token = create_access_token({"sub": user.email, "super": user.is_superuser})
    return {"access_token": access_token, "token_type": "bearer"}

# 🔑 Connexion sous-utilisateur avec email du parent
@router.post("/group_login")
def login_sub_user(data: GroupUserLogin, db: Session = Depends(get_db)):
    parent = db.query(User).filter(User.email == data.parent_email).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent user not found")
    sub = db.query(SubUser).filter(SubUser.username == data.username, SubUser.parent_user_id == parent.id).first()
    if not sub or not verify_password(data.password, sub.password_hash):
        raise HTTPException(status_code=400, detail="Invalid sub-user credentials")
    token = create_access_token({"sub": f"{parent.email}:{sub.username}", "role": sub.role})
    return {"access_token": token, "token_type": "bearer"}

# 👀 Afficher les sous-utilisateurs liés à un utilisateur principal
@router.get("/my_subusers", tags=["SubUsers"])
def list_my_subusers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subusers = db.query(SubUser).filter(SubUser.parent_user_id == current_user.id).all()
    return subusers



# 🔄 Modifier ses propres informations (utilisateur principal)
@router.put("/me", tags=["Users"])
def update_my_user(
    email: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    societe_ou_entreprise: Optional[str] = Body(None),
    username: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
    
):
    if email:
        current_user.email = email
    if password:
        current_user.password_hash = hash_password(password)
    if avatar_url:
        current_user.avatar_url = avatar_url
    if bio:
        current_user.bio = bio
    if societe_ou_entreprise:
        current_user.societe_ou_entreprise = societe_ou_entreprise
    if username:
        current_user.username = username
    db.commit()
    return {"message": "Informations utilisateur mises à jour avec succès."}

# 🔄 Modifier ses propres informations (sous-utilisateur connecté)
@router.put("/me-sub", tags=["SubUsers"])
def update_my_subuser(
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_sub: SubUser = Depends(get_current_sub_user)
):
    """
    ✏️ Route pour un sub-user : ne peut modifier que sa bio et son avatar
    """
    if avatar_url:
        current_sub.avatar_url = avatar_url
    if bio:
        current_sub.bio = bio

    db.commit()
    return {"message": "Profil sous-utilisateur mis à jour avec succès."}


@router.put("/subuser/{sub_id}", tags=["SubUsers"])
def update_subuser(
    sub_id: int,
    username: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    role: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    🔧 Route pour le parent : permet de modifier entièrement un sub-user qu'il a créé
    """
    sub = db.query(SubUser).filter(SubUser.id == sub_id, SubUser.parent_user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-user not found")

    if username: sub.username = username
    if password: sub.password_hash = hash_password(password)
    if role: sub.role = role
    if avatar_url: sub.avatar_url = avatar_url
    if bio: sub.bio = bio

    db.commit()
    return {"message": "Sub-user updated successfully"}


# ❌ Supprimer un sous-utilisateur
@router.delete("/subuser/{sub_id}", tags=["SubUsers"])
def delete_subuser(sub_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(SubUser).filter(SubUser.id == sub_id, SubUser.parent_user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-user not found")
    db.delete(sub)
    db.commit()
    return {"message": "Sub-user deleted successfully"}

# 🗑 Supprimer son propre compte (user principal + subusers)
@router.delete("/me", tags=["Users"])
def delete_own_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)):
    db.query(SubUser).filter(SubUser.parent_user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
    return {"message": "Your account and all sub-users have been deleted."}

# 👑 SUPERVISÉ - Supprimer un user (par un superUser uniquement)
@router.delete("/super/delete_user/{user_id}", tags=["Admin"])
def super_delete_user(user_id: int, current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(SubUser).filter(SubUser.parent_user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return {"message": "User and sub-users deleted by super admin."}

# 📋 Liste de tous les utilisateurs (réservé au super admin)
@router.get("/users", tags=["Admin"])
def list_all_users(current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

# 📋 Obtenir un utilisateur par son ID (réservé au super admin)
@router.get("/user/{user_id}", tags=["Admin"])
def get_user_by_id(user_id: int, current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 📋 Voir son propre profil (utilisateur principal connecté)
@router.get("/me", tags=["Users"])
def get_my_profile(
    current_user: User = Depends(get_current_user)
    ):
    return {"id": current_user.id, "email": current_user.email, "is_superuser": current_user.is_superuser, "bio": current_user.bio, "avatar_url": current_user.avatar_url, "is_main_user": current_user.is_main_user,  "username": current_user.username}

# 📋 Voir son propre profil (sous-utilisateur connecté)
@router.get("/me-sub", tags=["SubUsers"])
def get_my_subuser_profile(current_sub: SubUser = Depends(get_current_sub_user)):
    return {"id": current_sub.id, "username": current_sub.username, "role": current_sub.role, "bio": current_sub.bio, "avatar_url": current_sub.avatar_url}
