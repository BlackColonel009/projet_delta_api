from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_paiement import Paiement
from app.models.model_facture import Facture
from app.schemas.paiement_schema import PaiementCreate
from app.utils.logger import log_action
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.models.model_user import User

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

    paiement = Paiement(**data.dict())
    db.add(paiement)
    db.commit()

    # ➡ Mise à jour automatique du statut de la facture
    total_payé = sum(p.montant for p in facture.paiements)
    if total_payé >= facture.total_ttc:
        facture.statut = "payée"
        db.commit()

    # ➕ Historique
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
            "montant": p.montant,
            "date_paiement": p.date_paiement.strftime('%d/%m/%Y'),
            "moyen_paiement": p.moyen_paiement
        }
        for p in paiements
    ]
