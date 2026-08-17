from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.mail import send_email_message
from app.database import get_db
from app.models.model_client import Client
from app.models.model_intervention import Intervention, intervention_produits
from app.models.model_user import User
from app.schemas.intervention_schema import InterventionOut, InterventionCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from typing import Optional
from sqlalchemy import DateTime
from datetime import date



router = APIRouter(prefix="/interventions", tags=["Interventions"])

# ➕ Créer une intervention
@router.post("/", response_model=InterventionOut)
def create_intervention(
    
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.technicien]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    from app.models.model_produit import Produit

    intervention = Intervention(
        client_id=data.client_id,
        description=data.description,
        statut=data.statut,
        user_id=parent_user_id,
        produit_ex=data.produit_ex,
        caracteristique_ex=data.caracteristique_ex,
        commentaire_ex=data.commentaire_ex
    )


    produits = db.query(Produit).filter(Produit.id.in_(data.produits_ids)).all()
    intervention.produits = produits

    db.add(intervention)
    db.commit()
    db.refresh(intervention)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout intervention",
        type_entite="intervention",
        entite_id=intervention.id,
        details=f"Intervention pour client {intervention.client_id} par employé {intervention.user_id} — {intervention.statut}"
    )


    return InterventionOut(
        id=intervention.id,
        client_id=intervention.client_id,
        user_id=intervention.user_id,
        description=intervention.description,
        statut=intervention.statut,
        date_intervention=intervention.date_intervention,
        produits_ids=[p.id for p in produits],
        produit_ex=intervention.produit_ex,
        caracteristique_ex=intervention.caracteristique_ex,
        commentaire_ex=intervention.commentaire_ex,

    )


@router.put("/{intervention_id}", response_model=InterventionOut)
def update_intervention(
    intervention_id: int,
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.technicien])),
    background_tasks: BackgroundTasks = None
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    user = db.query(User).filter(User.id == parent_user_id).first()  # 👈 le user principal

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    intervention = db.query(Intervention).filter(
        Intervention.id == intervention_id,
        Intervention.user_id == parent_user_id
    ).first()


    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")

    statut_avant = intervention.statut  # pour détecter le changement
    

    # Mise à jour des champs
    intervention.client_id = data.client_id
    intervention.user_id = parent_user_id
    intervention.description = data.description
    intervention.statut = data.statut
    intervention.produit_ex = data.produit_ex
    intervention.caracteristique_ex = data.caracteristique_ex
    intervention.commentaire_ex = data.commentaire_ex

    # Mise à jour des produits liés
    from app.models.model_produit import Produit
    produits = db.query(Produit).filter(Produit.id.in_(data.produits_ids)).all()
    intervention.produits = produits
    
    facturation = intervention.commentaire_ex  # pour le mail
    
    db.commit()
    db.refresh(intervention)

    log_action(
        db=db,
        current_user=current_user,
        action="Mise à jour intervention",
        type_entite="intervention",
        entite_id=intervention.id,
        details=f"Intervention #{intervention.id} mise à jour"
    )

    # Si statut passe à "termine", on envoie un mail au client
    if statut_avant != "termine" and data.statut == "termine":
        client = db.query(Client).filter(Client.id == data.client_id).first()

        # Préparer le nom du ou des produits
        nom_produits = ""
        if produits:  # Si des produits liés existent
            nom_produits = ", ".join([p.nom for p in produits])
        elif data.produit_ex:
            nom_produits = data.produit_ex
        else:
            nom_produits = "votre équipement"

        if client and client.email:
            subject = f" Intervention terminée - {user.societe_ou_entreprise}"
            body = (
                f"Bonjour {client.nom},\n\n"
                f"L’intervention sur << {nom_produits} >> est maintenant terminée.\n"
                f"Vous pouvez passer à notre entreprise pour le récupérer.\n\n"
                f"L'intervention est Facturé à << {facturation} >>.\n\n"
                f"Merci de votre confiance.\n"
                f"L’équipe {user.societe_ou_entreprise}."
            )

            # Envoi en tâche de fond
            background_tasks.add_task(send_email_message, to_email=client.email, subject=subject, body=body)

    return InterventionOut(
        id=intervention.id,
        client_id=intervention.client_id,
        user_id=intervention.user_id,
        description=intervention.description,
        statut=intervention.statut,
        date_intervention=intervention.date_intervention,
        produits_ids=[p.id for p in produits],
        produit_ex=intervention.produit_ex,
        caracteristique_ex=intervention.caracteristique_ex,
        commentaire_ex=intervention.commentaire_ex,
    )



# 📋 Lister toutes les interventions
@router.get("/", response_model=List[InterventionOut])
def list_interventions(
    page: int = 1,
    limit: int = 10,
    date_min: Optional[date] = None,
    date_max: Optional[date] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.technicien]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    offset = (page - 1) * limit
    query = db.query(Intervention).filter(
        Intervention.user_id == (
            current_user.parent_user_id if not current_user.is_main_user else current_user.id
        ),
    )

    
    if date_min:
        query = query.filter(Intervention.date_intervention >= date_min)
    if date_max:
        query = query.filter(Intervention.date_intervention <= date_max)

    interventions = (
        query.order_by(Intervention.date_intervention.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
        
    print("🧪 Nombre d'interventions retournées:", len(interventions))  # ✅ ici c'est correct
    return [
        InterventionOut(
            id=i.id,
            client_id=i.client_id,
            user_id=i.user_id,
            description=i.description,
            statut=i.statut,
            date_intervention=i.date_intervention,
            produits_ids=[p.id for p in i.produits],
            produit_ex=i.produit_ex,
            caracteristique_ex=i.caracteristique_ex,
            commentaire_ex=i.commentaire_ex
        ) for i in interventions
    ]


# 🔍 Voir une intervention par ID
@router.get("/{intervention_id}", response_model=InterventionOut)
def get_intervention(
    intervention_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.technicien]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    i = db.query(Intervention).filter(
        Intervention.id == intervention_id,
        Intervention.user_id == parent_user_id
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")
    return InterventionOut(
        id=i.id,
        client_id=i.client_id,
        user_id=i.user_id,
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
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.technicien]))
):  
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    i = db.query(Intervention).filter(
        Intervention.id == intervention_id,
        Intervention.user_id == parent_user_id
    ).first()
    if not i:
        raise HTTPException(status_code=404, detail="Intervention non trouvée")
    db.delete(i)
    db.commit()
    
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression intervention",
        type_entite="intervention",
        entite_id=i.id,
        details=f"Intervention #{i.id} supprimée"
    )

    
    return {"message": "Intervention supprimée avec succès"}
