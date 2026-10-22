from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from types import SimpleNamespace
from typing import List, Optional
from app.database import get_db
from app.models.model_client import Client
from app.schemas.client_schema import (
    ClientCreate,
    ClientOut,
    ClientWelcomeEmailRequest,
)
from app.models.model_enterprise import Enterprise
from app.models.model_user import User
from app.core.mail import send_email_message
from app.email.branded_templates import client_welcome_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.utils.subscription_guard import enforce_subscription_quota
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)


router = APIRouter(prefix="/clients", tags=["Clients"])


@router.post("/{client_id}/welcome-email")
async def send_client_welcome_email(
    client_id: int,
    data: ClientWelcomeEmailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role(
            [
                RoleEnum.admin,
                RoleEnum.commercial,
                RoleEnum.secretaire,
                RoleEnum.technicien,
            ]
        )
    ),
):
    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            enterprise_scope_filter(Client, current_user),
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    if not client.email:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CLIENT_EMAIL_MISSING",
                "message": "Ce client n'a pas d'adresse e-mail enregistrée.",
            },
        )

    enterprise = db.query(Enterprise).filter(
        Enterprise.id == actor_enterprise_id(current_user)
    ).first()
    owner = db.query(User).filter(User.id == actor_owner_id(current_user)).first()
    if not enterprise or not owner:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")

    # Le template historique attend une identité de type utilisateur. Cette
    # identité éphémère garantit ici le nom, le logo et la couleur de l'annexe
    # active, sans modifier les paramètres globaux du propriétaire.
    brand = SimpleNamespace(
        societe_ou_entreprise=enterprise.name,
        email=enterprise.email or owner.email,
        logo_entreprise=enterprise.logo_url or owner.logo_entreprise,
        facture_color=enterprise.invoice_color or owner.facture_color,
        interface_language=data.language,
    )
    subject = (
        f"Welcome to {enterprise.name} 🎉"
        if data.language == "en"
        else f"Bienvenue chez {enterprise.name} 🎉"
    )
    sent = await send_email_message(
        to_email=client.email,
        subject=subject,
        body=client_welcome_email(user=brand, client_name=client.nom),
        reply_to=enterprise.email or owner.email,
        is_html=True,
    )
    if not sent:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EMAIL_DELIVERY_FAILED",
                "message": "Le service e-mail est momentanément indisponible.",
            },
        )

    log_action(
        db=db,
        current_user=current_user,
        action="Message de bienvenue client",
        type_entite="client",
        entite_id=client.id,
        details=f"E-mail de bienvenue envoyé à {client.nom} ({client.email})",
    )
    return {"message": "E-mail de bienvenue envoyé avec succès."}

# ➕ Créer un client
@router.post("/", response_model=ClientOut)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien]))
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    enforce_subscription_quota(
        db,
        current_user,
        "max_clients",
        db.query(Client).filter(Client.user_id == parent_user_id).count(),
        "clients",
    )
    # 🔐 Liaison automatique avec l'utilisateur connecté
    client = Client(
        **data.dict(),
        user_id=parent_user_id,
        enterprise_id=enterprise_id,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout client",
        type_entite="client",
        entite_id=client.id,
        details=f"Client ajouté : {client.nom} ({client.telephone})"
    )

    return client

# 📋 Lister tous les clients liés à l'utilisateur
@router.get("/", response_model=List[ClientOut])
def list_clients(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien] ))
):  
    query = db.query(Client).filter(
        enterprise_scope_filter(Client, current_user)
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (Client.nom.ilike(term)) | (Client.telephone.ilike(term))
        )
    return query.order_by(Client.id.desc()).offset(offset).limit(limit).all()


@router.get("/stats/count", response_model=dict)
def client_count_stats(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien])),
):
    count = db.query(func.count(Client.id)).filter(
        enterprise_scope_filter(Client, current_user)
    ).scalar()
    return {"count": int(count or 0)}

# @router.get("/", response_model=List[ClientOut])
# def get_clients(db: Session = Depends(get_db)):
#     return db.query(Client).all()  # temporairement sans filtre


# 🔍 Récupérer un client par ID
@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien]))
):
    parent_user_id = actor_owner_id(current_user)
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return client

# 🔄 Modifier un client
@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire]))
):
    parent_user_id = actor_owner_id(current_user)
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    for key, value in data.dict().items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Modification client",
        type_entite="client",
        entite_id=client.id,
        details=f"Client modifié : {client.nom} ({client.telephone})"
    )

    
    return client

# ❌ Supprimer un client
@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire]))
):  
    parent_user_id = actor_owner_id(current_user)
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    try:
        db.delete(client)
        db.commit()
        
        log_action(
            db=db,
            current_user=current_user,
            action="Suppression client",
            type_entite="client",
            entite_id=client.id,
            details=f"Client supprimé : {client.nom} ({client.telephone})"
        )
        
        return {"message": "Client supprimé avec succès"}
    
        
    
    except IntegrityError:
        db.rollback()
        
        log_action(
            db=db,
            current_user=current_user,
            action="Échec suppression client",
            type_entite="client",
            entite_id=client.id,
            details=f"Suppression refusée — client lié à une ou plusieurs ventes"
        )

        raise HTTPException(
            status_code=409,
            detail="Ce client ne peut pas être supprimé car il est lié à une ou plusieurs ventes."
        )
        
        
    
    

        
    
        
