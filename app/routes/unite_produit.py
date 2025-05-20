# app/routes/unite_produit.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_unite_produit import UniteProduit
from app.models.model_produit import Produit
from app.schemas.unite_produit_schema import AddUnitesRequest, UniteProduitOut
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from sqlalchemy.orm import joinedload
from datetime import datetime
from typing import List, Optional

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


# **************************CODE BARRE STEP**************************************

# 🧪 Enregistrer une série de codes-barres en statut temporaire (avant liaison produit)
@router.post("/temp", response_model=List[UniteProduitOut])
def store_temp_barcodes(
    barcodes: List[str],
    db: Session = Depends(get_db)
):
    results = []
    for code in barcodes:
        # Ignorer les doublons
        if db.query(UniteProduit).filter(UniteProduit.tracabilite == code).first():
            continue
        unit = UniteProduit(tracabilite=code, statut="temp")
        db.add(unit)
        results.append(unit)
    db.commit()
    return results

# 🔗 Lier une série de codes-barres (déjà scannés) à un produit
# 🔁 Mise à jour : lier des codes-barres à un produit
@router.post("/lier/{produit_id}")
def lier_barcodes_a_produit(
    produit_id: int,
    barcodes: List[str],
    db: Session = Depends(get_db)
):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    modifie = 0
    for code in barcodes:
        unite = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
        if unite:
            unite.produit_id = produit_id
            unite.statut = "disponible"
            modifie += 1
    db.commit()
    return {"message": f"{modifie} codes-barres liés au produit {produit.nom}"}


@router.post("/infos")
def get_produits_par_codes(barcodes: List[str], db: Session = Depends(get_db)):
    """
    🎯 Reçoit une liste de code_barres et retourne un regroupement par produit.
    Format retour : [{produit: {...}, codes: [code1, code2, ...]}, ...]
    """
    regroupement = {}

    for code in barcodes:
        unite = db.query(UniteProduit).filter(UniteProduit.tracabilite == code).first()
        if unite and unite.produit:
            pid = unite.produit.id
            if pid not in regroupement:
                regroupement[pid] = {
                    "produit": unite.produit,
                    "codes": []
                }
            regroupement[pid]["codes"].append(code)

    return list(regroupement.values())

@router.get("/unites-produits/by-barcode/{code}")
def get_unite_by_barcode(code: str, db: Session = Depends(get_db)):
    unite = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
    if not unite:
        raise HTTPException(status_code=404, detail="Introuvable")
    return unite
