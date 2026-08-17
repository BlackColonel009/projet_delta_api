from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.mail import send_email_message
from app.database import get_db
from app.models.model_commande import CommandeVente
from app.models.model_paiement import Paiement
from app.models.model_facture import Facture
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.schemas.paiement_schema import PaiementCreate
from app.utils.logger import log_action
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.models.model_user import User
from sqlalchemy import func

router = APIRouter(prefix="/paiements", tags=["Paiements"])


# ➕ Créer un paiement (admin + caissier)
@router.post("/", response_model=dict)
async def create_paiement(
    data: PaiementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    # 🔎 Récupérer la facture
    facture = db.query(Facture).filter(Facture.id == data.facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    # ➕ Enregistrer le paiement
    paiement = Paiement(**data.dict())
    db.add(paiement)
    db.commit()
    db.refresh(paiement)

    # 🧮 Total payé à ce jour
    total_paye = db.query(func.sum(Paiement.montant)).filter(
        Paiement.facture_id == facture.id
    ).scalar() or 0.0
    
    

    # 🔁 Si facture totalement payée
    if total_paye >= facture.total_ttc:
        facture.statut = "payée"

        if facture.type.value == "vente":
            commande = db.query(CommandeVente).filter(CommandeVente.id == facture.commande_id).first()
            if commande:
                
                commande.statut = "validée"
                # ✅ Marquer toutes les unités liées comme vendues
                unites = db.query(UniteProduit).filter(
                    UniteProduit.commande_vente_id == commande.id,
                    UniteProduit.statut.in_(["en cours", "disponible"])
                ).all()

                for unite in unites:
                    unite.statut = "vendu"
                    unite.date_modification = datetime.utcnow()

                    log_action(
                        db=db,
                        current_user=current_user,
                        action="Vente finalisée",
                        type_entite="unite_produit",
                        entite_id=unite.id,
                        details=f"Unité {unite.tracabilite} marquée comme vendue (facture #{facture.id})"
                    )
        elif facture.type.value == "achat":
            from app.models.model_commande import CommandeAchat
            commande = db.query(CommandeAchat).filter(CommandeAchat.id == facture.commande_id).first()
            if commande:
                commande.statut = "validée"
                
    elif total_paye > 0:
        facture.statut = "partielle"
    else:
        facture.statut = "non payée"

    db.commit()

     # 📧 Envoi de mail au client (si vente uniquement et email présent)
    if facture.client and facture.client.email:
        try:
            await envoyer_mail_confirmation_paiement(facture.client, facture, paiement, total_paye)
        except Exception as e:
            print("Erreur lors de l'envoi de l'email de paiement :", e)


    # 📝 Log global du paiement
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout paiement",
        type_entite="paiement",
        entite_id=paiement.id,
        details=f"Paiement de {paiement.montant:.2f} € pour Facture #{facture.id} via {paiement.moyen_paiement}"
    )

    return {"message": f"Paiement enregistré sur la facture #{facture.id}"}

async def envoyer_mail_confirmation_paiement(client, facture, paiement, total_paye):
    sujet = f"Confirmation de paiement - Facture #{facture.id}"
    devise = facture.user.devise if hasattr(facture, "user") else ""
    

    contenu = f"""
    Bonjour {client.nom},

    Nous vous confirmons la réception d’un paiement de {paiement.montant:.2f} {devise}
    pour la facture n°{facture.id} datée du {facture.date_creation.strftime('%d/%m/%Y')}.

    Statut actuel de la facture : {facture.statut.upper()}.
    Montant total dû : {facture.total_ttc:.2f} {devise}
    Total payé à ce jour : {facture.total_ttc if facture.statut == "payée" else total_paye:.2f} {devise}
    Moyen de paiement utilisé : {paiement.moyen_paiement}
    
    Merci pour votre confiance.

    — L’équipe {facture.user.societe_ou_entreprise if facture.user else "Trade Care"}
    """

    await send_email_message(
        to_email=client.email,
        subject=sujet,
        body=contenu,
    )



# 📋 Lister les paiements d'une facture (admin, caissier, comptable)
@router.get("/{facture_id}", response_model=list)
def list_paiements_for_facture(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable]))
):
    paiements = db.query(Paiement).filter(Paiement.facture_id == facture_id).all()
    return [
        {
            "id": p.id,
            "montant": p.montant,
            "date_paiement": p.date_paiement.strftime('%d/%m/%Y'),
            "moyen_paiement": p.moyen_paiement
        }
        for p in paiements
    ]
#supression paîements
@router.delete("/{paiement_id}", response_model=dict)
def delete_paiement(
    paiement_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    paiement = db.query(Paiement).filter(Paiement.id == paiement_id).first()
    if not paiement:
        raise HTTPException(status_code=404, detail="Paiement non trouvé")

    facture = paiement.facture

    db.delete(paiement)
    db.commit()

    # 🔁 Recalcul du statut de la facture après suppression
    total_paye = db.query(func.sum(Paiement.montant)).filter(
        Paiement.facture_id == facture.id
    ).scalar() or 0.0

    if total_paye >= facture.total_ttc:
        facture.statut = "payée"
    elif total_paye > 0:
        facture.statut = "partielle"
    else:
        facture.statut = "non payée"

        # ✅ Si c'était une vente, remettre les unités en "disponible"
        if facture.type.value == "vente":
            commande = db.query(CommandeVente).filter(CommandeVente.id == facture.commande_id).first()
            if commande:
                unites = db.query(UniteProduit).filter(
                    UniteProduit.commande_vente_id == commande.id,
                    UniteProduit.statut.in_(["en cours", "vendu"])
                ).all()

                for unite in unites:
                    unite.statut = "en cours"
                    unite.date_modification = datetime.utcnow()

                    log_action(
                        db=db,
                        current_user=current_user,
                        action="Réinitialisation unité",
                        type_entite="unite_produit",
                        entite_id=unite.id,
                        details=f"Unité {unite.tracabilite} remise à en cours (annulation paiement)"
                    )

    db.commit()

    # 📝 Log global
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression paiement",
        type_entite="paiement",
        entite_id=paiement_id,
        details=f"Paiement supprimé pour Facture #{facture.id} — Nouveau statut : {facture.statut}"
    )

    return {"message": "Paiement supprimé avec succès."}

