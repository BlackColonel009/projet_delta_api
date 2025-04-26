from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_paiement import Paiement
from app.models.model_facture import Facture
from app.schemas.paiement_schema import PaiementCreate

router = APIRouter(prefix="/paiements", tags=["Paiements"])

from app.utils.logger import log_action  # Assure-toi d'avoir ça importé en haut
from app.models.model_user import User
from app.utils.security import get_current_user

@router.post("/", response_model=dict)
def create_paiement(
    data: PaiementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ récupérer l'utilisateur connecté
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

    # ➡ LOG de l'action paiement
    log_action(
        db=db,
        user_id=current_user.id,
        action="Ajout Paiement",
        type_entite="paiement",
        entite_id=paiement.id,
        details=f"Paiement de {paiement.montant:.2f} € pour Facture #{facture.id} via {paiement.moyen_paiement}"
    )

    return {"message": f"Paiement enregistré sur la facture #{facture.id}"}

# Lister les paiements d'une facture
@router.get("/{facture_id}", response_model=list)
def list_paiements_for_facture(facture_id: int, db: Session = Depends(get_db)):
    paiements = db.query(Paiement).filter(Paiement.facture_id == facture_id).all()
    return [
        {
            "montant": p.montant,
            "date_paiement": p.date_paiement.strftime('%d/%m/%Y'),
            "moyen_paiement": p.moyen_paiement
        }
        for p in paiements
    ]
