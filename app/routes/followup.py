from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_client import Client
from app.models.model_clientfollowup import ClientFollowup, FollowupStatus
from app.models.model_commande import CommandeVente


from app.repo_scheduler.scheduler_ai import run_followup_scheduler
from app.schemas.followup_schema import UpdateDelaiRelanceSchema
from app.utils.logger import log_action
from app.utils.permissions import check_role, RoleEnum
from app.utils.security import get_current_user

router_followup = APIRouter(prefix="/followups", tags=["Suivi client"])


# ⚠️ Route de test manuelle pour déclencher l'envoi des messages
@router_followup.get("/test_scheduler")
def test_suivi_scheduler(
    db: Session = Depends(get_db),
    # current_user=Depends(check_role([RoleEnum.admin]))  # réservé aux admins
):
    """
    🔁 Déclenche manuellement le scheduler de suivi client pour test.
    """
    run_followup_scheduler(db)
    return {"message": "Scheduler exécuté avec succès"}

@router_followup.get("/count")
def get_unique_followup_clients_count(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    count = db.query(ClientFollowup.client_id).filter(
        ClientFollowup.type_followup == "fidélisation",
        ClientFollowup.user_id == current_user.id
    ).distinct().count()
    
    return {"count": count}


@router_followup.post("/{client_id}/desactiver")
def desactiver_suivis_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    """
    Désactive tous les suivis liés à un client donné.
    """
    suivis = db.query(ClientFollowup).filter(
        ClientFollowup.client_id == client_id,
        ClientFollowup.user_id == current_user.id,
        ClientFollowup.type_followup == FollowupStatus.fidelisation.value
    ).all()

    if not suivis:
        raise HTTPException(status_code=404, detail="Aucun suivi trouvé pour ce client")

    for s in suivis:
        s.type_followup = FollowupStatus.desactive.value

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suivis désactivés",
        type_entite="client_followup",
        entite_id=client_id,
        details=f"Tous les suivis du client #{client_id} ont été désactivés"
    )

    return {"message": "Tous les suivis du client désactivés avec succès"}

# Activer un suivi client (réservé aux admins)
@router_followup.post("/{client_id}/activer")
def activer_suivis_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    """
    Active tous les suivis liés à un client donné.
    """
    suivis = db.query(ClientFollowup).filter(
        ClientFollowup.client_id == client_id,
        ClientFollowup.user_id == current_user.id,
        ClientFollowup.type_followup == FollowupStatus.desactive.value
    ).all()

    if not suivis:
        raise HTTPException(status_code=404, detail="Aucun suivi trouvé pour ce client")

    suivis_actives = []
    suivis_supprimes = []

    for s in suivis:
        # Vérifie si une commande liée est annulée
        if s.commandes and s.commandes.statut == "annulée":
            db.delete(s)
            suivis_supprimes.append(s.id)
        else:
            s.type_followup = FollowupStatus.fidelisation.value
            suivis_actives.append(s.id)

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suivis activés",
        type_entite="client_followup",
        entite_id=client_id,
        details=f"Tous les suivis du client #{client_id} ont été activés"
    )

    return {"message": "Tous les suivis du client activés avec succès"}

# Lister les suivis clients avec filtres, pagination et sécurisation par user_id
@router_followup.get("/")
def lister_suivis_clients(
    client_id: Optional[int] = Query(None, description="Filtrer par ID client"),
    statut: Optional[FollowupStatus] = Query(None, description="Filtrer par statut"),
    type_followup: Optional[str] = Query(None, description="Filtrer par type de suivi"),
    limit: int = Query(20, ge=1, le=100, description="Nombre max de résultats"),
    offset: int = Query(0, ge=0, description="Offset pagination"),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.caissier, RoleEnum.gestionnaire_stock]))
):
    """
    Liste paginée des suivis clients actifs pour l'utilisateur connecté.
    """
    query = db.query(ClientFollowup).join(Client).join(CommandeVente).filter(
        ClientFollowup.user_id == current_user.id  # Sécurisation par user_id
    )

    if client_id:
        query = query.filter(ClientFollowup.client_id == client_id)
    if statut:
        query = query.filter(ClientFollowup.statut == statut)
    if type_followup:
        query = query.filter(ClientFollowup.type_followup == type_followup)

    total = query.count()
    suivis = query.order_by(ClientFollowup.date_prochain_envoi.asc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "resultats": [
            {
                "id": s.id,
                "client_id": s.client_id,
                "client_nom": s.client.nom if s.client else None,
                "commande_id": s.commande_id,
                "type": s.type_followup,
                "statut": s.statut.value,
                "date_prochain_envoi": s.date_prochain_envoi,
                "date_achat": s.date_achat,
            }
            for s in suivis
        ]
    }


# Détails d’un suivi client individuel avec sécurisation user_id
@router_followup.get("/{followup_id}")
def get_followup_details(
    followup_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.caissier, RoleEnum.gestionnaire_stock]))
):
    """
    Récupère les détails d’un suivi client spécifique pour l’utilisateur connecté.
    """
    followup = db.query(ClientFollowup).filter(
        ClientFollowup.id == followup_id,
        ClientFollowup.user_id == current_user.id  # Sécurisation par user_id
    ).first()

    if not followup:
        raise HTTPException(status_code=404, detail="Suivi client introuvable ou accès refusé")

    return {
        "id": followup.id,
        "client_id": followup.client_id,
        "client_nom": followup.client.nom if followup.client else None,
        "commande_id": followup.commande_id,
        "type": followup.type_followup,
        "statut": followup.statut.value,
        "date_achat": followup.date_achat,
        "date_prochain_envoi": followup.date_prochain_envoi,
        "commande_statut": followup.commandes.statut if followup.commandes else None
    }


# Récupérer les suivis d'un client spécifique pour l'utilisateur connecté
@router_followup.get("/client/{client_id}")
def get_followups_for_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.caissier, RoleEnum.gestionnaire_stock]))
):
    """
    Récupère la liste des suivis client pour un client donné, pour l'utilisateur connecté.
    """
    followups = db.query(ClientFollowup).filter(
        ClientFollowup.client_id == client_id,
        ClientFollowup.user_id == current_user.id
    ).all()

    return [
        {
            "id": f.id,
            "type": f.type_followup,
            "statut": f.statut.value,
            "date_achat": f.date_achat,
            "date_prochain_envoi": f.date_prochain_envoi,
            # Ajoute d'autres champs si besoin
        }
        for f in followups
    ]

# mise à jour du délai avant relance pour un retard de paiement
@router_followup.post("/{followup_id}/delai-relance")
def update_delai_relance(
    followup_id: int,
    payload: UpdateDelaiRelanceSchema,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial]))
):
    followup = db.query(ClientFollowup).filter(
        ClientFollowup.id == followup_id,
        ClientFollowup.user_id == current_user.id
    ).first()

    if not followup:
        raise HTTPException(
            status_code=404,
            detail="Suivi introuvable ou accès refusé"
        )

    # 🔕 si désactivé, on autorise quand même la config
    followup.delai_avant_relance = payload.delai_avant_relance

    # 🔁 reset anti-harcèlement
    followup.dernier_envoi = None

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Mise à jour délai relance",
        type_entite="client_followup",
        entite_id=followup.id,
        details=f"Délai relance mis à {payload.delai_avant_relance} jours"
    )

    return {
        "message": "Délai de relance mis à jour avec succès",
        "followup_id": followup.id,
        "delai_avant_relance": followup.delai_avant_relance
    }

