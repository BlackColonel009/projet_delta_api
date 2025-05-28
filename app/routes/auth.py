# 🔐 ROUTES AVANCÉES AUTHENTIFICATION
# Fichier : app/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from app.models.model_client import Client
from app.models.model_commande import CommandeAchat, CommandeVente
from app.models.model_fournisseur import Fournisseur
from app.models.model_historique_general import Historique
from app.models.model_historique_intervention import HistoriqueIntervention
from app.models.model_intervention import Intervention
from app.models.model_produit import Produit
from app.models.model_rapport import Rapport
from app.schemas.user_schema import SubUserOut, UserCreate, SubUserCreate, UserLogin, GroupUserLogin
from app.models.model_user import User, SubUser
from app.models.model_role import Role
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_sub_user, require_role, 
    require_super_user, require_any_role, require_main_user
)
from app.database import get_db
from app.utils.logger import log_action

router = APIRouter()

# 🔒 Créer un utilisateur principal (Single user)
@router.post("/register", tags=["Authentification"])
def register_user(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        is_main_user=data.is_main_user,
        is_superuser=False,
        account_type=data.account_type,
        societe_ou_entreprise=data.societe_ou_entreprise,
        devise=data.devise or "€", 
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Inscription utilisateur",
    #     type_entite="utilisateur",
    #     entite_id=new_user.id,
    #     details=f"Nouvel utilisateur inscrit : {new_user.email}"
    # )

    return {"message": "User created successfully"}

# 🔒 Créer un sous-utilisateur sous un utilisateur principal
@router.post("/register_sub", tags=["Authentification"])
def register_sub_user(
    data: SubUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_user)
):
    parent = db.query(User).filter(User.email == data.parent_email).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent user not found")

    if not db.query(Role).filter(Role.name == data.role).first():
        raise HTTPException(status_code=400, detail="Rôle non autorisé")

    new_sub = SubUser(
        username=data.username,
        password_hash=hash_password(data.password),
        bio = data.bio,
        role=data.role,
        parent_user_id=parent.id
    )
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Ajout sub-user",
    #     type_entite="sub-user",
    #     entite_id=new_sub.id,
    #     details=f"SubUser ajouté : {new_sub.username} pour le parent {parent.email}"
    # )

    return {"message": "Sub-user created successfully"}

# 🔑 Connexion utilisateur principal
@router.post("/login", tags=["Authentification"])
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    access_token = create_access_token({"sub": user.email, "super": user.is_superuser})

    # ✅ Simulation d’un current_user (car pas encore dans un Depends)
    class UserTokenProxy:
        def __init__(self, user_obj):
            self.id = user_obj.id
            self.is_main_user = True

    fake_current_user = UserTokenProxy(user)

    log_action(
        db=db,
        current_user=fake_current_user,
        action="Connexion utilisateur",
        type_entite="utilisateur",
        entite_id=user.id,
        details=f"L'utilisateur {user.email} s'est connecté"
    )

    return {"access_token": access_token, "token_type": "bearer"}


# 🔑 Connexion sous-utilisateur
@router.post("/group_login")
def login_sub_user(data: GroupUserLogin, db: Session = Depends(get_db)):
    parent = db.query(User).filter(User.email == data.parent_email).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent user not found")

    sub = db.query(SubUser).filter(
        SubUser.username == data.username,
        SubUser.parent_user_id == parent.id
    ).first()

    if not sub or not verify_password(data.password, sub.password_hash):
        raise HTTPException(status_code=400, detail="Invalid sub-user credentials")

    token = create_access_token({
        "sub": f"{parent.email}:{sub.username}",
        "role": sub.role
    })

    # ✅ Appel avec current_user simulé (sub-user)
    class SubUserTokenProxy:
        def __init__(self, sub_id, parent_id):
            self.id = sub_id
            self.parent_user_id = parent_id
            self.is_main_user = False

    fake_current_user = SubUserTokenProxy(sub.id, parent.id)

    log_action(
        db=db,
        current_user=fake_current_user,
        action="Connexion sub-user",
        type_entite="sub-user",
        entite_id=sub.id,
        details=f"Le sub-user {sub.username} s'est connecté via {parent.email}"
    )

    return {"access_token": token, "token_type": "bearer"}


# 👀 Lister mes sub-users
@router.get("/my_subusers", tags=["SubUsers"])
def list_my_subusers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(SubUser).filter(SubUser.parent_user_id == current_user.id).all()

# 🔄 Modifier infos principal
@router.put("/me", tags=["Users"])
def update_my_user(
    email: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    societe_ou_entreprise: Optional[str] = Body(None),
    logo_entreprise : Optional[str] = Body(None),
    username: Optional[str] = Body(None),
    devise: Optional[str] = Body(None),
    telephone: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if email: current_user.email = email
    if password: current_user.password_hash = hash_password(password)
    if avatar_url: current_user.avatar_url = avatar_url
    if bio: current_user.bio = bio
    if societe_ou_entreprise: current_user.societe_ou_entreprise = societe_ou_entreprise
    if username: current_user.username = username
    if devise: current_user.devise = devise
    if telephone: current_user.telephone = telephone
    if logo_entreprise: current_user.logo_entreprise = logo_entreprise
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Modification utilisateur principal",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Mise à jour de ses propres informations"
    )

    return {"message": "Informations utilisateur mises à jour avec succès."}

# 🔄 Modifier infos subuser
@router.put("/me-sub", tags=["SubUsers"])
def update_my_subuser(
    bio: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    telephone: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_sub: SubUser = Depends(get_current_sub_user)
):
    if bio is not None:
        current_sub.bio = bio
    if avatar_url is not None:
        current_sub.avatar_url = avatar_url
    if telephone is not None:
        current_sub.telephone = telephone
    db.commit()
    db.refresh(current_sub)
    
    # log_action(
    #     db=db,
    #     sub_user_id=current_sub.id,  # ✅ Utilise le bon champ
    #     action="Modification profil sub-user",
    #     type_entite="sub-user",
    #     entite_id=current_sub.id,
    #     details=f"Sub-user {current_sub.username} a modifié son profil"
    # )

    return {
        "id": current_sub.id,
        "username": current_sub.username,
        "role": current_sub.role,
        "bio": current_sub.bio,
        "avatar_url": current_sub.avatar_url,
        "telephone": current_sub.telephone
    }



# 🔧 Modifier un subuser (parent)
@router.put("/subuser/{sub_id}", tags=["SubUsers"])
def update_subuser(
    sub_id: int,
    username: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    role: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    telephone : Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    
    sub = db.query(SubUser).filter(SubUser.id == sub_id, SubUser.parent_user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-user not found")

    if username: sub.username = username
    if password: sub.password_hash = hash_password(password)
    if role: sub.role = role
    if avatar_url: sub.avatar_url = avatar_url
    if bio: sub.bio = bio
    if telephone: sub.telephone = telephone
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Mise à jour sub-user",
        type_entite="sub-user",
        entite_id=sub.id,
        details=f"Sub-user {sub.username} mis à jour"
    )

    return {"message": "Sub-user updated successfully"}

# ❌ Supprimer subuser
@router.delete("/subuser/{sub_id}", tags=["SubUsers"])
def delete_subuser(sub_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(SubUser).filter(SubUser.id == sub_id, SubUser.parent_user_id == current_user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-user not found")
    db.delete(sub)
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression sub-user",
        type_entite="sub-user",
        entite_id=sub.id,
        details=f"Sub-user {sub.username} supprimé"
    )

    return {"message": "Sub-user deleted successfully"}

# 🗑 Supprimer son propre compte
@router.delete("/me", tags=["Users"])
def delete_own_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(SubUser).filter(SubUser.parent_user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression de compte",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="L'utilisateur a supprimé son compte"
    )

    return {"message": "Your account and all sub-users have been deleted."}

# 👑 Supprimer un user par le superuser
@router.delete("/super/delete_user/{user_id}", tags=["Admin"])
def super_delete_user(user_id: int, current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.query(SubUser).filter(SubUser.parent_user_id == user.id).delete()
    db.delete(user)
    db.commit()

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Suppression user par superuser",
    #     type_entite="utilisateur",
    #     entite_id=user_id,
    #     details=f"User {user.email} supprimé par superadmin"
    # )

    return {"message": "User and sub-users deleted by super admin."}

# 📋 Lister tous les users
@router.get("/users", tags=["Admin"])
def list_all_users(current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    return db.query(User).all()

# 📃 Voir un user
@router.get("/user/{user_id}", tags=["Admin"])
def get_user_by_id(user_id: int, current_super: User = Depends(require_super_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 👁 Voir son profil
@router.get("/me", tags=["Users"])
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_superuser": current_user.is_superuser,
        "bio": current_user.bio,
        "avatar_url": current_user.avatar_url,
        "is_main_user": current_user.is_main_user,
        "username": current_user.username,
        "societe_ou_entreprise": current_user.societe_ou_entreprise,
        "logo_entreprise": current_user.logo_entreprise,
        "account_type": current_user.account_type,
        "devise": current_user.devise,
        "telephone" : current_user.telephone,
    }

# 👁 Voir son profil subuser
@router.get("/me-sub",response_model=SubUserOut, tags=["SubUsers"])
def get_my_subuser_profile(current_sub: SubUser = Depends(get_current_sub_user),  db: Session = Depends(get_db)):
    parent = db.query(User).filter(User.id == current_sub.parent_user_id).first()
    return {
        "id": current_sub.id,
        "username": current_sub.username,
        "role": current_sub.role,
        "bio": current_sub.bio,
        "avatar_url": current_sub.avatar_url,
        "devise": parent.devise,  # ✅ ici
        "telephone" : current_sub.telephone,
        "main_user_data": {
                "societe_ou_entreprise": parent.societe_ou_entreprise,
                "logo_entreprise": parent.logo_entreprise,
                "devise": parent.devise,
            }
    }

