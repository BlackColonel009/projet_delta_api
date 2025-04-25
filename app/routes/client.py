from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_client import Client
from app.schemas.client_schema import ClientCreate, ClientOut
from pydantic import BaseModel

router = APIRouter(prefix="/clients", tags=["Clients"])

# ➕ Créer un client
@router.post("/", response_model=ClientOut)
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**data.dict())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client

# 📋 Lister tous les clients
@router.get("/", response_model=List[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).all()

# 🔍 Récupérer un client par ID
@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    return client

# 🔄 Modifier un client
@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientCreate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    for key, value in data.dict().items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client

# ❌ Supprimer un client
@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")
    db.delete(client)
    db.commit()
    return {"message": "Client supprimé avec succès"}
