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
from app.schemas.user_schema import CompanyThemeUpdate, SessionLockUpdate, SessionUnlockRequest, SubUserOut, UserCreate, SubUserCreate, UserLogin, GroupUserLogin
from app.models.model_user import User, SubUser
from app.models.model_role import Role
from app.services.subscription_service import create_trial_subscription
from app.utils.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_sub_user, get_active_user, require_role, 
    require_super_user, require_any_role, require_main_user
)
from app.database import get_db
from app.utils.logger import log_action
from app.utils.permissions import All_required
from app.utils.subscription_guard import (
    enforce_subscription_quota,
    require_subscription_feature,
)

router = APIRouter()


@router.put("/session-lock", tags=["Users"])
def update_session_lock(
    data: SessionLockUpdate,
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
):
    """Configure le verrouillage d'inactivité du compte connecté."""
    if data.session_lock_minutes > 0 and not data.password:
        raise HTTPException(
            status_code=400,
            detail="Définissez un mot de passe de verrouillage d’au moins 5 caractères",
        )
    current_user.session_lock_minutes = data.session_lock_minutes
    current_user.session_lock_configured = True
    current_user.session_lock_password_hash = (
        hash_password(data.password)
        if data.session_lock_minutes > 0 and data.password
        else None
    )
    db.commit()
    db.refresh(current_user)
    return {
        "session_lock_minutes": current_user.session_lock_minutes,
        "session_lock_configured": current_user.session_lock_configured,
        "message": (
            "Verrouillage automatique désactivé"
            if current_user.session_lock_minutes == 0
            else f"Session verrouillée après {current_user.session_lock_minutes} minutes d’inactivité"
        ),
    }


@router.post("/session-lock/unlock", tags=["Users"])
def unlock_session(
    data: SessionUnlockRequest,
    current_user=Depends(get_active_user),
):
    password_hash = current_user.session_lock_password_hash
    if not password_hash or not verify_password(data.password, password_hash):
        raise HTTPException(
            status_code=400,
            detail="Mot de passe de verrouillage incorrect",
        )
    return {"unlocked": True}

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
    
    db.flush()  # Parfois suffisant
    
    db.commit()
    
    # 🧠 Fix Render: propagation vers DB réelle
    _ = db.query(User).filter(User.email == data.email).first()
    import time
    time.sleep(0.5)
    
    db.refresh(new_user)
    
    # 2️⃣ Créer automatiquement l'abonnement trial
    create_trial_subscription(db, user_id=new_user.id)
    
    # ✅ On génère le token directement
    access_token = create_access_token({
        "sub": new_user.email,
    })

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Inscription utilisateur",
    #     type_entite="utilisateur",
    #     entite_id=new_user.id,
    #     details=f"Nouvel utilisateur inscrit : {new_user.email}"
    # )

    return {
        "message": "User created successfully",
        "access_token": access_token,
        "token_type": "bearer"
    }

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
    if parent.id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez créer un sous-utilisateur que pour votre entreprise.",
        )

    enforce_subscription_quota(
        db,
        current_user,
        "max_sub_users",
        db.query(SubUser).filter(SubUser.parent_user_id == parent.id).count(),
        "sous-utilisateurs",
    )

    if not db.query(Role).filter(Role.name == data.role).first():
        raise HTTPException(status_code=400, detail="Rôle non autorisé")

    new_sub = SubUser(
        username=data.username,
        password_hash=hash_password(data.password),
        bio = data.bio,
        role=data.role,
        parent_user_id=parent.id,
        devise = parent.devise

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
    print(f"🔎 Recherche utilisateur avec {form_data.username}")
    if not user:
        print("❌ Aucun utilisateur trouvé")
    else:
        print("✅ Utilisateur trouvé :", user.email)
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


@router.put("/theme", tags=["Users"])
def update_company_theme(
    data: CompanyThemeUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(All_required()),
    _=Depends(require_subscription_feature("custom_theme")),
):
    """Enregistre le thème commun à toute l'entreprise."""
    if not current_user.is_main_user and str(current_user.role).lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent modifier les paramètres.",
        )
    owner = current_user if current_user.is_main_user else db.query(User).filter(
        User.id == current_user.parent_user_id
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    owner.app_theme = data.app_theme
    owner.theme_mode = data.theme_mode
    db.commit()
    db.refresh(owner)
    return {
        "app_theme": owner.app_theme,
        "theme_mode": owner.theme_mode,
    }


@router.put("/facture-theme", tags=["Users"])
def update_company_invoice_theme(
    facture_color: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
    _=Depends(require_subscription_feature("theme_colors")),
):
    if not current_user.is_main_user and str(current_user.role).lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent modifier les paramètres.",
        )
    if not facture_color.startswith("#") or len(facture_color) not in (7, 9):
        raise HTTPException(status_code=422, detail="Couleur de facture invalide")
    owner = current_user if current_user.is_main_user else db.query(User).filter(
        User.id == current_user.parent_user_id
    ).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    owner.facture_color = facture_color.upper()
    db.commit()
    db.refresh(owner)
    return {"facture_color": owner.facture_color}


@router.put("/me-sub/password", tags=["SubUsers"])
def update_own_subuser_password(
    password: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_sub: SubUser = Depends(get_current_sub_user),
):
    if str(current_sub.role).lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent modifier les paramètres.",
        )
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Le mot de passe doit contenir au moins 8 caractères",
        )
    current_sub.password_hash = hash_password(password)
    db.commit()
    return {"message": "Mot de passe modifié avec succès"}

# 🔄 Modifier infos principal
@router.put("/me", tags=["Users"])
def update_my_user(
    email: Optional[str] = Body(None),
    password: Optional[str] = Body(None),
    avatar_url: Optional[str] = Body(None),
    bio: Optional[str] = Body(None),
    societe_ou_entreprise: Optional[str] = Body(None),
    logo_entreprise: Optional[str] = Body(None),
    addresse: Optional[str] = Body(None),
    nif: Optional[str] = Body(None),
    tva: Optional[float] = Body(None),
    username: Optional[str] = Body(None),
    devise: Optional[str] = Body(None),
    telephone: Optional[str] = Body(None),
    facture_color: Optional[str] = Body(None),
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
    if addresse:
        current_user.addresse = addresse
    if nif:
        current_user.nif = nif
    if tva is not None:
        current_user.tva = tva
    if username:
        current_user.username = username
    if devise:
        current_user.devise = devise
    if telephone:
        current_user.telephone = telephone
    if logo_entreprise:
        current_user.logo_entreprise = logo_entreprise
    if facture_color:
        current_user.facture_color = facture_color
        print(f"[DEBUG] Mise à jour facture_color: {facture_color}")

    # Propagation aux subusers des champs modifiés (TVA, NIF, adresse)
    subusers = db.query(SubUser).filter(SubUser.parent_user_id == current_user.id).all()
    for subuser in subusers:
        if tva is not None:
            subuser.tva = tva
        if nif is not None:
            subuser.nif = nif
        if addresse is not None:
            subuser.addresse = addresse

    db.commit()
    print("[DEBUG] Commit effectué")

    log_action(
        db=db,
        current_user=current_user,
        action="Modification utilisateur principal",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Mise à jour de ses propres informations avec propagation aux subusers"
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
        "is_main_user": False,
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
    sub = db.query(SubUser).filter(
        SubUser.id == sub_id,
        SubUser.parent_user_id == current_user.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sous-utilisateur introuvable")

    if username is not None:
        normalized_username = username.strip()
        if not normalized_username:
            raise HTTPException(status_code=400, detail="Le pseudo est obligatoire")

        duplicate = db.query(SubUser).filter(
            SubUser.parent_user_id == current_user.id,
            SubUser.username == normalized_username,
            SubUser.id != sub_id,
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Ce pseudo est déjà utilisé dans votre entreprise",
            )
        sub.username = normalized_username

    if password is not None:
        if password and len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Le mot de passe doit contenir au moins 8 caractères",
            )
        if password:
            sub.password_hash = hash_password(password)

    if role is not None:
        normalized_role = role.strip()
        if not normalized_role:
            raise HTTPException(status_code=400, detail="Le rôle est obligatoire")
        sub.role = normalized_role
    if avatar_url is not None:
        sub.avatar_url = avatar_url.strip() or None
    if bio is not None:
        sub.bio = bio.strip() or None
    if telephone is not None:
        sub.telephone = telephone.strip() or None

    db.commit()
    db.refresh(sub)

    log_action(
        db=db,
        current_user=current_user,
        action="Mise à jour sub-user",
        type_entite="sub-user",
        entite_id=sub.id,
        details=f"Sub-user {sub.username} mis à jour"
    )

    return {
        "message": "Sous-utilisateur mis à jour avec succès",
        "sub_user": {
            "id": sub.id,
            "username": sub.username,
            "role": sub.role,
            "bio": sub.bio,
            "telephone": sub.telephone,
            "avatar_url": sub.avatar_url,
            "created_at": sub.created_at,
        },
    }

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
        "nif": current_user.nif,
        "tva": current_user.tva,
        "addresse": current_user.addresse,
        "account_type": current_user.account_type,
        "devise": current_user.devise,
        "telephone" : current_user.telephone,
        "app_theme": current_user.app_theme or "tradecare",
        "theme_mode": current_user.theme_mode or "system",
        "session_lock_minutes": current_user.session_lock_minutes or 0,
        "session_lock_configured": current_user.session_lock_configured or False,
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
        "session_lock_minutes": current_sub.session_lock_minutes or 0,
        "session_lock_configured": current_sub.session_lock_configured or False,
        "main_user_data": {
                "societe_ou_entreprise": parent.societe_ou_entreprise,
                "logo_entreprise": parent.logo_entreprise,
                "devise": parent.devise,
                "nif": parent.nif,
                "tva": parent.tva,
                "addresse": parent.addresse,
                "facture_color": parent.facture_color,
                "app_theme": parent.app_theme or "tradecare",
                "theme_mode": parent.theme_mode or "system",
            }
    }

