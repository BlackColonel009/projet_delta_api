# 📡 ROUTES POUR LA FACTURATION
# Fichier : app/routes/facture.py

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_facture import Facture, LigneFacture
from app.models.model_unite_produit import UniteProduit
from app.schemas.facture_schema import FactureOut, FactureCreate
from fastapi.responses import FileResponse
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

# 🔍 Lire une facture avec ses lignes
# 🔍 Lire une facture avec ses lignes
@router.get("/{facture_id}", response_model=FactureOut)
def get_facture(
    facture_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock , RoleEnum.commercial]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    facture = db.query(Facture)\
        .options(joinedload(Facture.fournisseur), joinedload(Facture.client))\
        .filter(
            Facture.id == facture_id,
            Facture.user_id == parent_user_id
        )\
        .first()


    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")

    total_paye = sum(p.montant for p in facture.paiements)  # Assure-toi que la relation existe

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
        "total_paye": sum(p.montant for p in facture.paiements),  # ✅ injecté ici
        "tva": facture.tva,
        "lignes": facture.lignes
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

    factures = db.query(Facture).filter(Facture.user_id == parent_user_id).all()
    result = []

    for f in factures:
        # 🔢 Calcul du total payé à partir des paiements liés
        total_paye = sum(p.montant for p in f.paiements) if f.paiements else 0.0

        # 🔁 Construction manuelle de chaque entrée enrichie
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
            fournisseur=f.fournisseur,# 🟢 Ajouté ici
            lignes=f.lignes         # 🟢 Ajouté ici
            
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
