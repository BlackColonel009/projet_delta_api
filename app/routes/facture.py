# 📡 ROUTES POUR LA FACTURATION
# Fichier : app/routes/facture.py

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_clientfollowup import ClientFollowup
from app.models.model_commande import CommandeVente
from app.models.model_depot import Depot
from app.models.model_facture import Facture, LigneFacture, TypeFacture
from app.models.model_facture_depot import FactureDepot
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.routes import depot
from app.schemas.facture_depot_schema import FactureDepotOut
from app.schemas.facture_schema import FactureOut, FactureCreate
from fastapi.responses import FileResponse
from app.utils.logger import log_action
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from sqlalchemy.orm import joinedload
import os

router = APIRouter(prefix="/factures", tags=["Facturation"])

# ➕ Créer une facture complète
@router.post("/", response_model=FactureOut)
def create_facture(
    data: FactureCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock, RoleEnum.commercial]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    total_ht = sum(l.quantite * l.prix_unitaire for l in data.lignes)
    total_ttc = total_ht * (1 + data.tva / 100)

    facture = Facture(
        type=data.type,
        client_id=data.client_id,
        fournisseur_id=data.fournisseur_id,
        remarques=data.remarques,
        tva=data.tva,
        total_ht=total_ht,
        total_ttc=total_ttc,
        user_id=parent_user_id,  # 🔐 Liaison sécurisée
        
    )

    db.add(facture)
    db.flush()  # Pour générer facture.id

    for ligne in data.lignes:
        ligne_facture = LigneFacture(
            facture_id=facture.id,
            produit_id=ligne.produit_id,
            description=ligne.description,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            total_ligne=ligne.quantite * ligne.prix_unitaire
        )
        db.add(ligne_facture)

    db.commit()
    db.refresh(facture)
    return facture

#changer le type de la facture
@router.patch("/{facture_id}/type", response_model=dict)
def update_facture_type(
    facture_id: int,
    nouveau_type: TypeFacture,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([
        RoleEnum.admin, 
        RoleEnum.gestionnaire_stock
    ]))
):
    facture = db.query(Facture).filter(Facture.id == facture_id).first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    ancien_type = facture.type
    facture.type = nouveau_type
    db.commit()

    return {
        "message": f"Type de la facture #{facture_id} mis à jour de '{ancien_type.value}' à '{nouveau_type.value}'"
    }

# 🔍 Lire une facture avec ses lignes
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload


@router.get("/{facture_id}", response_model=FactureOut)
def get_facture(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([
        RoleEnum.admin,
        RoleEnum.gestionnaire_stock,
        RoleEnum.commercial
    ]))
):
    parent_user_id = (
        current_user.parent_user_id
        if not current_user.is_main_user
        else current_user.id
    )

    facture = db.query(Facture)\
        .options(
            joinedload(Facture.fournisseur),
            joinedload(Facture.client),
            joinedload(Facture.lignes)
                .joinedload(LigneFacture.produit)
                .joinedload(Produit.unites)
        )\
        .filter(
            Facture.id == facture_id,
            Facture.user_id == parent_user_id
        )\
        .first()

    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    # Récupérer toutes les unités liées à la commande vente (si facture liée)
    all_unites = []
    if facture.commande_id:
        all_unites = db.query(UniteProduit).filter(
            UniteProduit.commande_vente_id == facture.commande_id
        ).order_by(UniteProduit.id).all()

    index_unites = 0
    lignes_data = []

    for ligne in facture.lignes:
        produit = ligne.produit
        quantite = ligne.quantite or 0

        # Prendre uniquement les unités correspondantes à la quantité de la ligne
        unites_for_line = all_unites[index_unites : index_unites + quantite]
        index_unites += quantite

        lignes_data.append({
            "id": ligne.id,
            "description": ligne.description,
            "quantite": quantite,
            "prix_unitaire": ligne.prix_unitaire,
            "total_ligne": ligne.total_ligne,
            "produit": {
                "id": produit.id,
                "nom": produit.nom,
                "caracteristiques": produit.caracteristiques or {}
            } if produit else None,
            "unites": [
                {
                    "id": u.id,
                    "produit_id": u.produit_id,
                    "tracabilite": u.tracabilite,
                    "code_barre": u.code_barre,
                    "statut": u.statut,
                    "date_creation": u.date_creation,
                    "date_modification": u.date_modification,
                }
                for u in unites_for_line
            ]
        })

    total_paye = sum(p.montant for p in facture.paiements)

    return {
        "id": facture.id,
        "type": facture.type,
        "client_id": facture.client_id,
        "client": facture.client,
        "fournisseur_id": facture.fournisseur_id,
        "fournisseur": facture.fournisseur,
        "date_creation": facture.date_creation,
        "statut": facture.statut,
        "remarques": facture.remarques,
        "total_ht": facture.total_ht,
        "total_ttc": facture.total_ttc,
        "total_paye": total_paye,
        "tva": facture.tva,
        "lignes": lignes_data
    }


# 🔄 Mettre à jour le statut d'une facture
@router.patch("/{facture_id}/statut", response_model=dict)
def update_facture_statut(
    facture_id: int,
    statut: str,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock , RoleEnum.commercial]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    facture = db.query(Facture).filter(
        Facture.id == facture_id,
        Facture.user_id == parent_user_id
    ).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    facture.statut = statut
    db.commit()
    return {"message": f"Statut de la facture #{facture_id} mis à jour en '{statut}'"}

# 📋 Lister toutes les factures de l'utilisateur connecté
# 📋 Lister toutes les factures de l'utilisateur connecté avec total_paye
@router.get("/", response_model=List[FactureOut])
def list_factures(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock, RoleEnum.commercial, RoleEnum.caissier]))
):
    parent_user_id = (
        current_user.parent_user_id if not current_user.is_main_user else current_user.id
    )

    factures = db.query(Facture)\
        .options(
            joinedload(Facture.fournisseur),
            joinedload(Facture.client),
            joinedload(Facture.lignes).joinedload(LigneFacture.produit)
        )\
        .filter(Facture.user_id == parent_user_id).all()

    result = []

    for f in factures:
        total_paye = sum(p.montant for p in f.paiements) if f.paiements else 0.0

        lignes_data = []
        for ligne in f.lignes:
            produit = ligne.produit
            lignes_data.append({
                "id": ligne.id,
                "description": ligne.description,
                "quantite": ligne.quantite,
                "prix_unitaire": ligne.prix_unitaire,
                "total_ligne": ligne.total_ligne,
                "produit": {
                    "id": produit.id,
                    "nom": produit.nom,
                    "caracteristiques": produit.caracteristiques or {},
                } if produit else None
            })

        result.append(FactureOut(
            id=f.id,
            total_ttc=f.total_ttc,
            statut=f.statut,
            total_ht=f.total_ht,
            tva=f.tva,
            type=f.type,
            client_id=f.client_id,
            fournisseur_id=f.fournisseur_id,
            date_creation=f.date_creation,
            remarques=f.remarques,
            total_paye=total_paye,
            client=f.client,
            fournisseur=f.fournisseur,
            lignes=lignes_data
        ))

    return result

#modification d'unité
@router.patch("/facture/{facture_id}/valider-unites")
def valider_unites_apres_paiement(facture_id: int, db: Session = Depends(get_db)):
    facture = db.query(Facture).filter(Facture.id == facture_id).first()
    if not facture or facture.statut != "payée":
        raise HTTPException(status_code=400, detail="Facture non payée")

    for ligne in facture.commande.lignes:
        for code in ligne.codes:
            unite = db.query(UniteProduit).filter(
                UniteProduit.tracabilite == code,
                UniteProduit.statut == "en cours"
            ).first()
            if unite:
                unite.statut = "vendu"
                unite.date_modification = datetime.utcnow()
    db.commit()
    return {"message": "Unités marquées comme vendues"}

#Annuler la facture et remettre les unités en place
@router.post("/{facture_id}/annuler", response_model=dict)
def annuler_facture(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier]))
):
    from app.models.model_commande import CommandeVente, CommandeAchat
    from app.models.model_unite_produit import UniteProduit

    facture = db.query(Facture).filter(Facture.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    if facture.statut == "annulée":
        raise HTTPException(status_code=400, detail="Cette facture a déjà été annulée")

    commande = db.query(CommandeVente).filter(CommandeVente.id == facture.commande_id).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande associée non trouvée")

    facture.statut = "annulée"

    # 🧾 Traitement selon le type de facture
    if facture.type.value == "vente":
        commande = db.query(CommandeVente).filter(CommandeVente.id == facture.commande_id).first()
        if not commande:
            raise HTTPException(status_code=404, detail="Commande de vente non trouvée")

        commande.statut = "annulée"
        

        # ✅ Réinitialiser les unités à "disponible"
        unites = db.query(UniteProduit).filter(
            UniteProduit.commande_vente_id == commande.id,
            UniteProduit.statut.in_(["en cours", "vendu"])
        ).all()

        for unite in unites:
            unite.statut = "disponible"
            unite.date_modification = datetime.utcnow()

            log_action(
                db=db,
                current_user=current_user,
                action="Annulation vente",
                type_entite="unite_produit",
                entite_id=unite.id,
                details=f"Unité {unite.tracabilite} remise à disponible après annulation facture #{facture.id}"
            )
        

        # ----------------------------------------------
        # Suppression automatique des suivis liés à cette commande annulée
        suivis_a_supprimer = db.query(ClientFollowup).filter(
            ClientFollowup.commande_id == facture.commande_id
        ).all()

        for suivi in suivis_a_supprimer:
            log_action(
                db=db,
                current_user=current_user,
                action="Suppression suivi auto après annulation facture",
                type_entite="client_followup",
                entite_id=suivi.id,
                details=f"Suivi supprimé car commande #{facture.commande_id} annulée via facture #{facture.id}"
            )
            db.delete(suivi)

        
        # ----------------------------------------------

    elif facture.type.value == "achat":
        commande = db.query(CommandeAchat).filter(CommandeAchat.id == facture.commande_id).first()
        if not commande:
            raise HTTPException(status_code=404, detail="Commande d'achat non trouvée")

        commande.statut = "annulée"
        
        # ✅ Supprimer les unités associées à cette commande
        unites = db.query(UniteProduit).filter(
            UniteProduit.commande_achat_id == commande.id
        ).all()

        for unite in unites:
            log_action(
                db=db,
                current_user=current_user,
                action="Suppression unité achat",
                type_entite="unite_produit",
                entite_id=unite.id,
                details=f"Unité {unite.tracabilite} supprimée après annulation achat facture #{facture.id}"
            )
            db.delete(unite)

    else:
        raise HTTPException(status_code=400, detail="Type de facture non pris en charge")
    
    # ❌ Supprimer les traces dans ClientProduit
    from app.models.model_client_produit import ClientProduit

    client_produits = db.query(ClientProduit).filter(
        ClientProduit.commande_id == facture.commande_id
    ).all()

    for cp in client_produits:
        cp.note = "rejeté"
        cp.date_modification = datetime.utcnow()

        log_action(
            db=db,
            current_user=current_user,
            action="Marquage rejet",
            type_entite="client_produit",
            entite_id=cp.id,
            details=f"Note changée en 'rejeté' suite à l'annulation de la facture #{facture.id}"
        )





    db.commit()

    # 📝 Log global
    log_action(
        db=db,
        current_user=current_user,
        action="Facture annulée",
        type_entite="facture",
        entite_id=facture.id,
        details=f"Facture #{facture.id} annulée (type : {facture.type.value})"
    )

    return {"message": f"Facture #{facture.id} annulée avec succès."}

@router.post("/facture-rapide/{depot_id}", response_model=FactureDepotOut)
def create_quick_facture_from_depot(
    depot_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    depot = db.query(Depot).filter(Depot.id == depot_id).first()
    if not depot:
        raise HTTPException(status_code=404, detail="Dépôt introuvable")

    if depot.statut != "retire":
        raise HTTPException(status_code=400, detail="Le dépôt n'est pas encore retiré.")

    existing_facture = db.query(FactureDepot).filter_by(depot_id=depot_id).first()
    if existing_facture:
        raise HTTPException(status_code=400, detail="Une facture existe déjà pour ce dépôt.")

    montant_ht = depot.prix_total or 0
    tva = 0  # tu peux adapter ici
    montant_ttc = montant_ht + tva

    facture = FactureDepot(
        depot_id=depot.id,
        client_id=depot.client_id,
        montant_ht=montant_ht,
        tva=tva,
        montant_ttc=montant_ttc,
        statut="en_attente",
        date_facture=datetime.utcnow()
    )

    db.add(facture)
    depot.statut = "retire"
    db.commit()
    db.refresh(facture)

    return facture

@router.get("/by-depot/{depot_id}", response_model=FactureDepotOut)
def get_facture_by_depot(depot_id: int, db: Session = Depends(get_db)):
    facture = db.query(FactureDepot).filter(FactureDepot.depot_id == depot_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Pas de facture pour ce dépôt")
    return facture
