from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
def create_paiement(
    data: PaiementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    facture = db.query(Facture).filter(Facture.id == data.facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    # ➕ Enregistrement du paiement
    paiement = Paiement(**data.dict())
    db.add(paiement)
    db.commit()
    db.refresh(paiement)

    # 🔁 Calcul du total payé
    total_paye = db.query(func.sum(Paiement.montant)).filter(
        Paiement.facture_id == facture.id
    ).scalar() or 0.0

    # 🎯 Mise à jour du statut de la facture
    if total_paye >= facture.total_ttc:
        facture.statut = "payée"

        # ✅ Mise à jour des unités (statut → "vendu")
        if facture.type.value == "vente":
            commande = db.query(CommandeVente).filter(CommandeVente.id == facture.commande_id).first()
            if commande:
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

                # ✅ Mise à jour des stocks (Produit.quantite)
                for ligne in commande.lignes:
                    produit = db.query(Produit).filter(Produit.id == ligne.produit_id).first()
                    if produit:
                        produit.quantite -= ligne.quantite
                        produit.date_modification = datetime.utcnow()
                        log_action(
                            db=db,
                            current_user=current_user,
                            action="Stock mis à jour",
                            type_entite="produit",
                            entite_id=produit.id,
                            details=f"{ligne.quantite} unité(s) retirée(s) du stock pour {produit.nom}"
                        )

    elif total_paye > 0:
        facture.statut = "partielle"
    else:
        facture.statut = "non payée"

    db.commit()

    # 🧾 Log global du paiement
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout paiement",
        type_entite="paiement",
        entite_id=paiement.id,
        details=f"Paiement de {paiement.montant:.2f} € pour Facture #{facture.id} via {paiement.moyen_paiement}"
    )

    return {"message": f"Paiement enregistré sur la facture #{facture.id}"}


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

    db.commit()

    # Log
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression paiement",
        type_entite="paiement",
        entite_id=paiement_id,
        details=f"Paiement supprimé pour Facture #{facture.id}"
    )

    return {"message": "Paiement supprimé avec succès."}
