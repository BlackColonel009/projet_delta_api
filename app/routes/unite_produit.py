# app/routes/unite_produit.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_unite_produit import UniteProduit
from app.models.model_produit import Produit
from app.schemas.unite_produit_schema import AddUnitesRequest
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from sqlalchemy.orm import joinedload
from datetime import datetime

router = APIRouter(prefix="/unites-produit", tags=["Unités Produit"])

@router.post("/add/{produit_id}")
def add_unites_to_produit(
    produit_id: int,
    data: AddUnitesRequest,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut == "disponible",
        Produit.user_id == parent_user_id
    ).all()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    created = []
    for i in range(1, data.nombre + 1):
        tracabilite = f"{data.prefixe}{produit_id}-{str(i).zfill(4)}"
        unite = UniteProduit(
            produit_id=produit.id,
            tracabilite=tracabilite,
            statut="disponible",
            date_creation=datetime.utcnow()
        )
        db.add(unite)
        created.append(tracabilite)

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Ajout unités",
        type_entite="produit",
        entite_id=produit.id,
        details=f"{data.nombre} unités créées avec QR pour produit {produit.nom}"
    )

    return {"message": "Unités ajoutées avec succès", "tracabilites": created}


#reccuperer par id
@router.get("/produits/{produit_id}/unites")
def list_unites_for_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    from app.models.model_unite_produit import UniteProduit

    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut == "disponible",
        Produit.user_id == parent_user_id
    ).all()

    return [
        {
            "id": u.id,
            "tracabilite": u.tracabilite,
            "statut": u.statut,
            "date_creation": u.date_creation.strftime('%Y-%m-%d %H:%M')
        }
        for u in unites
    ]

#reccuperer unité disponible
@router.get("/disponibles")
def list_unites_disponibles(
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut == "disponible",
        Produit.user_id == parent_user_id
    ).all()
    return [
        {
            "id": u.id,
            "produit_id": u.produit_id,
            "nom_produit": u.produit.nom,
            "tracabilite": u.tracabilite,
            "date_creation": u.date_creation.strftime('%Y-%m-%d %H:%M')
        }
        for u in unites
    ]
    
#suppression d'unité-produit
@router.delete("/{unite_id}")
def delete_unite_produit(
    unite_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    unite = db.query(UniteProduit).filter(UniteProduit.id == unite_id).first()
    if not unite:
        raise HTTPException(status_code=404, detail="Unité non trouvée")

    produit = unite.produit  # pour info dans les logs

    db.delete(unite)
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression unité",
        type_entite="unite_produit",
        entite_id=unite.id,
        details=f"Unité QR supprimée : {unite.tracabilite} (produit {produit.nom})"
    )

    return {"message": f"Unité supprimée : {unite.tracabilite}"}