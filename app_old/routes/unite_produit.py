# app/routes/unite_produit.py

from fastapi import APIRouter, Depends, HTTPException, Body
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
    # 🔍 Récupérer le produit
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut == "disponible",
        Produit.user_id == parent_user_id
    ).all()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    # # 🚫 Vérification : si le produit contient déjà des codes-barres scannés
    # if produit.a_des_barcodes:
    #     raise HTTPException(
    #         status_code=400,
    #         detail="❌ Ce produit contient déjà des unités avec code-barres. L’ajout d’unités avec QR est désactivé pour éviter les conflits."
    #     )

    created = []
    
    if data.tracabilites:
        # 🧠 Mode manuel : utiliser les tracabilités données
        if len(data.tracabilites) != data.nombre:
            raise HTTPException(status_code=400, detail="Le nombre de tracabilités fournies ne correspond pas à 'nombre'.")

        for tracabilite in data.tracabilites:
            unite = UniteProduit(
                produit_id=produit.id,
                tracabilite=tracabilite,
                statut="disponible",
                date_creation=datetime.utcnow()
            )
            db.add(unite)
            created.append(tracabilite)

    else:
        # ⚙️ Mode automatique
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
        details=f"{data.nombre} unités ajoutées {'manuellement' if data.tracabilites else 'automatiquement'} pour produit {produit.nom}"
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
        UniteProduit.produit_id == produit_id,  # ✅ filtre ajouté
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
@router.get("/disponibles")  # ou /toutes si tu veux encore plus large
def list_unites_visibles(
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    unites = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.statut.in_(["disponible", "indisponible", "vendu", "en cours"]),  # ✅ inclut les deux
        Produit.user_id == parent_user_id
    ).all()

    return [
        {
            "id": u.id,
            "produit_id": u.produit_id,
            "nom_produit": u.produit.nom,
            "statut": u.statut,
            "tracabilite": u.tracabilite,
            "date_creation": u.date_creation.strftime('%Y-%m-%d %H:%M'),
            "date_modification": u.date_modification.strftime('%Y-%m-%d %H:%M') if u.date_modification else None
        }
        for u in unites
    ]

    
    

# ✅ 2. Route de purge des unités "temp"
@router.delete("/purge-temp")
def purge_temp_units(
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    deleted = db.query(UniteProduit).filter(
        UniteProduit.statut == "temp",
        UniteProduit.produit_id == None
    ).delete(synchronize_session=False)
    db.commit()

    # log_action(
    #     db=db,
    #     current_user=current_user,
    #     action="Purge",
    #     type_entite="unite_produit",
    #     entite_id=None,
    #     details=f"{deleted} unités temporaires supprimées"
    # )

    return {
        "message": f"{deleted} unités 'temp' supprimées.",
        "deleted_count": deleted
    }

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

    produit = unite.produit  # récupération avant suppression

    # Supprimer l'unité
    unite.statut = "indisponible"
    unite.date_modification = datetime.utcnow()
    db.commit()

    # 🔁 Recalculer la quantité restante
    quantite_restante = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit.id,
        UniteProduit.statut == "disponible"
    ).count()

    # Mettre à jour le champ produit.quantite
    produit.quantite = quantite_restante
    db.commit()

    # Logger
    log_action(
        db=db,
        current_user=current_user,
        action="Suppression unité",
        type_entite="unite_produit",
        entite_id=unite.id,
        details=f"Unité QR supprimée : {unite.tracabilite} (produit {produit.nom}) quantité restante: {produit.quantite}"
    )

    return {
        "message": f"Unité supprimée : {unite.tracabilite}",
        "quantite_restante": quantite_restante,
        "produit_id": produit.id,
        "produit_nom": produit.nom
    }

# **************************CODE BARRE STEP**************************************

# 🧪 Enregistrer une série de codes-barres en statut temporaire (avant liaison produit)
@router.post("/temp")
def store_temp_barcodes(barcodes: List[str], db: Session = Depends(get_db)):
    inserted = 0
    for code in barcodes:
        # Vérifie si le code existe déjà
        exist = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
        if exist:
            continue  # ne pas dupliquer

        unite = UniteProduit(
            tracabilite=code,
            code_barre=code,
            statut="temp",
            produit_id=None,
            date_creation=datetime.utcnow()
        )
        db.add(unite)
        inserted += 1

    db.commit()
    return {"message": f"{inserted} unités temporaires enregistrées."}

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
    regroupement = {}
    invalid_codes = []

    for code in barcodes:
        unite = db.query(UniteProduit).filter(
            UniteProduit.tracabilite == code,
            UniteProduit.produit_id.isnot(None),
            UniteProduit.statut == "disponible"
        ).first()

        if not unite or not unite.produit:
            invalid_codes.append(code)
            continue

        pid = unite.produit.id
        if pid not in regroupement:
            regroupement[pid] = {
                "produit": unite.produit,
                "codes": []
            }
        regroupement[pid]["codes"].append(code)

    return {
        "produits": list(regroupement.values()),
        "invalid_codes": invalid_codes
    }


# ✅ 3. Rechercher une unité via code_barre
@router.get("/by-barcode/{code}", response_model=UniteProduitOut)
def get_unite_by_barcode(code: str, db: Session = Depends(get_db)):
    unite = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
    if not unite:
        raise HTTPException(status_code=404, detail="Code-barre introuvable")
    return unite

# #modification d'unité statut
# @router.put("/set-statut/{unite_id}")
# def set_statut_unite(
#     unite_id: int,
#     statut: str = Body(...),
#     db: Session = Depends(get_db),
#     current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
# ):
#     unite = db.query(UniteProduit).filter(UniteProduit.id == unite_id).first()
#     if not unite:
#         raise HTTPException(status_code=404, detail="Unité non trouvée")

#     unite.statut = statut
#     unite.date_modification = datetime.utcnow()
#     db.commit()

#     return {
#         "message": f"Statut de l'unité {unite.tracabilite} mis à jour : {statut}"
#     }
