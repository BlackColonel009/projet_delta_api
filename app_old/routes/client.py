from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_client import Client
from app.schemas.client_schema import ClientCreate, ClientOut
from sqlalchemy.exc import IntegrityError
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action


router = APIRouter(prefix="/clients", tags=["Clients"])

# ➕ Créer un client
@router.post("/", response_model=ClientOut)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    # 🔐 Liaison automatique avec l'utilisateur connecté
    client = Client(**data.dict(), user_id=parent_user_id)
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
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.secretaire, RoleEnum.technicien] ))
):  
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    return db.query(Client).filter(Client.user_id == parent_user_id).all()

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
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == parent_user_id
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
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == parent_user_id
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
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == parent_user_id
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
        
        
    
    

        
    
        
