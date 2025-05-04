from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_intervention import Intervention, intervention_produits
from app.schemas.intervention_schema import InterventionOut, InterventionCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router = APIRouter(prefix="/interventions", tags=["Interventions"])

# ➕ Créer une intervention
@router.post("/", response_model=InterventionOut)
def create_intervention(
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "technicien"]))  # 🔐 contrôle de rôle
):
    from app.models.model_produit import Produit

    intervention = Intervention(
        client_id=data.client_id,
        employe_id=data.employe_id,
        description=data.description,
        statut=data.statut,
        user_id=current_user.id
    )

    produits = db.query(Produit).filter(Produit.id.in_(data.produits_ids)).all()
    intervention.produits = produits

    db.add(intervention)
    db.commit()
    db.refresh(intervention)

    return InterventionOut(
        id=intervention.id,
        client_id=intervention.client_id,
        employe_id=intervention.employe_id,
        description=intervention.description,
        statut=intervention.statut,
        date_intervention=intervention.date_intervention,
        produits_ids=[p.id for p in produits]
    )

# 📋 Lister toutes les interventions
@router.get("/", response_model=List[InterventionOut])
def list_interventions(
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "technicien"]))
):
    interventions = db.query(Intervention).filter(Intervention.user_id == current_user.id).all()
    return [
        InterventionOut(
            id=i.id,
            client_id=i.client_id,
            employe_id=i.employe_id,
            description=i.description,
            statut=i.statut,
            date_intervention=i.date_intervention,
            produits_ids=[p.id for p in i.produits]
        ) for i in interventions
    ]

# 🔍 Voir une intervention par ID
@router.get("/{intervention_id}", response_model=InterventionOut)
def get_intervention(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "technicien"]))
):
    i = db.query(Intervention).filter(
        Intervention.id == intervention_id,
        Intervention.user_id == current_user.id
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")
    return InterventionOut(
        id=i.id,
        client_id=i.client_id,
        employe_id=i.employe_id,
        description=i.description,
        statut=i.statut,
        date_intervention=i.date_intervention,
        produits_ids=[p.id for p in i.produits]
    )

# ❌ Supprimer une intervention
@router.delete("/{intervention_id}")
def delete_intervention(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "technicien"]))
):
    i = db.query(Intervention).filter(
        Intervention.id == intervention_id,
        Intervention.user_id == current_user.id
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")
    db.delete(i)
    db.commit()
    return {"message": "Intervention supprimée avec succès"}
