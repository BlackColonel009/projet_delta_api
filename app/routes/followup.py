from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_client import Client
from app.models.model_clientfollowup import ClientFollowup, FollowupStatus
from app.models.model_commande import CommandeVente
from app.models.model_facture import Facture, TypeFacture


from app.repo_scheduler.scheduler_ai import run_followup_scheduler
from app.schemas.followup_schema import (
    ClientFollowupSettingsUpdate,
    PaymentReminderSettingsUpdate,
    UpdateDelaiRelanceSchema,
)
from app.utils.logger import log_action
from app.utils.permissions import check_role, RoleEnum
from app.utils.security import get_active_user
from app.services.enterprise_service import enterprise_scope_filter

router_followup = APIRouter(prefix="/followups", tags=["Suivi client"])


def _company_user_id(current_user) -> int:
    return (
        current_user.id
        if current_user.is_main_user
        else current_user.parent_user_id
    )


def _payment_reminder_payload(followup, facture_id: int) -> dict:
    if not followup:
        return {
            "facture_id": facture_id,
            "available": False,
            "enabled": False,
            "start_after_days": 2,
            "next_send_at": None,
        }
    return {
        "facture_id": facture_id,
        "followup_id": followup.id,
        "available": True,
        "enabled": getattr(followup, "payment_reminder_enabled", True),
        "start_after_days": followup.delai_avant_relance or 2,
        "next_send_at": followup.date_prochain_envoi,
    }


def _client_followup_payload(client) -> dict:
    return {
        "client_id": client.id,
        "enabled": getattr(client, "followup_enabled", True),
        "thank_you_delay_days": getattr(
            client, "followup_thank_you_delay_days", 1
        ),
        "recommendations_enabled": getattr(
            client, "followup_recommendations_enabled", True
        ),
        "first_recommendation_delay_days": getattr(
            client, "followup_first_recommendation_delay_days", 10
        ),
        "recommendation_interval_days": getattr(
            client, "followup_recommendation_interval_days", 14
        ),
    }


# ⚠️ Route de test manuelle pour déclencher l'envoi des messages
@router_followup.get("/test_scheduler")
async def test_suivi_scheduler(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin])),
):
    """
    🔁 Déclenche manuellement le scheduler de suivi client pour test.
    """
    await run_followup_scheduler(
        db,
        enterprise_id=current_user.active_enterprise_id,
    )
    return {"message": "Scheduler exécuté avec succès"}

@router_followup.get("/count")
def get_unique_followup_clients_count(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([
        RoleEnum.admin,
        RoleEnum.commercial,
        RoleEnum.caissier,
        RoleEnum.gestionnaire_stock,
    ])),
):
    count = db.query(ClientFollowup.client_id).filter(
        ClientFollowup.type_followup == "fidélisation",
        enterprise_scope_filter(ClientFollowup, current_user),
    ).distinct().count()
    
    return {"count": count}


@router_followup.get("/invoice/{facture_id}/payment-reminder")
def get_invoice_payment_reminder(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.commercial, RoleEnum.caissier])
    ),
):
    """Retourne la programmation de relance propre a une facture de vente."""
    facture = db.query(Facture).filter(
        Facture.id == facture_id,
        enterprise_scope_filter(Facture, current_user),
    ).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")

    followup = None
    if facture.commande_id and facture.type == TypeFacture.vente:
        followup = db.query(ClientFollowup).filter(
            ClientFollowup.commande_id == facture.commande_id,
            enterprise_scope_filter(ClientFollowup, current_user),
            ClientFollowup.type_followup == "relance_paiement",
        ).first()
    return _payment_reminder_payload(followup, facture_id)


@router_followup.put("/invoice/{facture_id}/payment-reminder")
def update_invoice_payment_reminder(
    facture_id: int,
    payload: PaymentReminderSettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial])),
):
    """Programme le debut des relances sans affecter les autres factures."""
    facture = db.query(Facture).filter(
        Facture.id == facture_id,
        enterprise_scope_filter(Facture, current_user),
        Facture.type == TypeFacture.vente,
    ).first()
    if not facture or not facture.commande_id:
        raise HTTPException(
            status_code=404,
            detail="Cette facture ne possede pas de rappel de paiement.",
        )

    followup = db.query(ClientFollowup).filter(
        ClientFollowup.commande_id == facture.commande_id,
        enterprise_scope_filter(ClientFollowup, current_user),
        ClientFollowup.type_followup == "relance_paiement",
    ).first()
    if not followup:
        raise HTTPException(
            status_code=404,
            detail=(
                "Aucune relance de paiement active : la facture est peut-etre "
                "deja soldee ou annulee."
            ),
        )

    followup.payment_reminder_enabled = payload.enabled
    followup.delai_avant_relance = payload.start_after_days
    start = followup.date_achat or facture.date_creation or datetime.utcnow()
    followup.date_prochain_envoi = start + timedelta(
        days=payload.start_after_days
    )
    followup.dernier_envoi = None
    db.commit()
    db.refresh(followup)

    log_action(
        db=db,
        current_user=current_user,
        action="Configuration rappel de paiement",
        type_entite="client_followup",
        entite_id=followup.id,
        details=(
            f"Facture #{facture_id} : relance "
            f"{'activee' if payload.enabled else 'desactivee'}, debut apres "
            f"{payload.start_after_days} jour(s)"
        ),
    )
    return _payment_reminder_payload(followup, facture_id)


@router_followup.get("/client/{client_id}/settings")
def get_client_followup_settings(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role(
            [
                RoleEnum.admin,
                RoleEnum.commercial,
                RoleEnum.caissier,
                RoleEnum.gestionnaire_stock,
            ]
        )
    ),
):
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return _client_followup_payload(client)


@router_followup.put("/client/{client_id}/settings")
def update_client_followup_settings(
    client_id: int,
    payload: ClientFollowupSettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.commercial])),
):
    """Personnalise le parcours apres paiement pour un seul client."""
    client = db.query(Client).filter(
        Client.id == client_id,
        enterprise_scope_filter(Client, current_user),
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    client.followup_enabled = payload.enabled
    client.followup_thank_you_delay_days = payload.thank_you_delay_days
    client.followup_recommendations_enabled = payload.recommendations_enabled
    client.followup_first_recommendation_delay_days = (
        payload.first_recommendation_delay_days
    )
    client.followup_recommendation_interval_days = (
        payload.recommendation_interval_days
    )

    now = datetime.utcnow()
    loyalty_followups = db.query(ClientFollowup).filter(
        ClientFollowup.client_id == client_id,
        enterprise_scope_filter(ClientFollowup, current_user),
        ClientFollowup.type_followup == "fidélisation",
        ClientFollowup.statut != FollowupStatus.termine,
    ).all()
    for followup in loyalty_followups:
        if followup.statut == FollowupStatus.en_attente:
            start = followup.date_achat or now
            followup.date_prochain_envoi = start + timedelta(
                days=payload.thank_you_delay_days
            )
        elif followup.statut == FollowupStatus.message_1_envoye:
            followup.date_prochain_envoi = now + timedelta(
                days=payload.first_recommendation_delay_days
            )
        else:
            followup.date_prochain_envoi = now + timedelta(
                days=payload.recommendation_interval_days
            )

    db.commit()
    db.refresh(client)
    log_action(
        db=db,
        current_user=current_user,
        action="Configuration suivi apres paiement",
        type_entite="client_followup",
        entite_id=client.id,
        details=(
            f"Client #{client.id} : suivi "
            f"{'actif' if payload.enabled else 'inactif'}, remerciement a "
            f"J+{payload.thank_you_delay_days}, recommandations "
            f"{'actives' if payload.recommendations_enabled else 'inactives'}"
        ),
    )
    return _client_followup_payload(client)


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
        enterprise_scope_filter(ClientFollowup, current_user),
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
        enterprise_scope_filter(ClientFollowup, current_user),
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
        enterprise_scope_filter(ClientFollowup, current_user),
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
        enterprise_scope_filter(ClientFollowup, current_user),
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
        enterprise_scope_filter(ClientFollowup, current_user),
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
        enterprise_scope_filter(ClientFollowup, current_user),
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

