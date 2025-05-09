# 📦 ROUTES POUR Commande Vente et Achat

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.model_produit import Produit
from app.models.model_client import Client
from app.models.model_fournisseur import Fournisseur
from app.models.model_commande import CommandeVente, LigneCommandeVente, CommandeAchat, LigneCommandeAchat
from app.services.generate_facture_from_commande import generate_facture_from_commande, generate_facture_pdf
from app.schemas.commande_schema import CommandeVenteCreate, CommandeAchatCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
import os

router_ventes = APIRouter(prefix="/commandes-ventes", tags=["Commandes Ventes"])
router_achats = APIRouter(prefix="/commandes-achats", tags=["Commandes Achats"])

# ➕ Créer une commande vente
@router_ventes.post("/")
def create_commande_vente(
    data: CommandeVenteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    client = db.query(Client).filter(Client.id == data.client_id, Client.user_id == parent_user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    commande = CommandeVente(
        client_id=data.client_id,
        tva_appliquee=data.tva_appliquee,
        user_id=current_user.id
    )
    db.add(commande)
    db.commit()
    db.refresh(commande)

    total_ht = 0

    for ligne_data in data.lignes:
        produit = db.query(Produit).filter(
            Produit.id == ligne_data.produit_id,
            Produit.user_id == parent_user_id
        ).first()

        if not produit:
            raise HTTPException(status_code=404, detail=f"Produit introuvable pour l'ID {ligne_data.produit_id}")

        if produit.quantite < ligne_data.quantite:
            raise HTTPException(status_code=400, detail=f"Stock insuffisant pour {produit.nom}")

        produit.quantite -= ligne_data.quantite
        total_ligne = produit.prix_vente * ligne_data.quantite
        total_ht += total_ligne

        ligne_commande = LigneCommandeVente(
            commande_id=commande.id,
            produit_id=produit.id,
            description=produit.nom,
            quantite=ligne_data.quantite,
            prix_unitaire=produit.prix_vente,
            total_ligne=total_ligne
        )
        db.add(ligne_commande)

        # ✅ Si vente via QR, marquer l’unité et logger
        if ligne_data.unite_id:
            unite = db.query(UniteProduit).filter(UniteProduit.id == ligne_data.unite_id).first()
            if not unite:
                raise HTTPException(status_code=404, detail="Unité non trouvée")
            unite.statut = "vendu"

            log_action(
                db=db,
                current_user=current_user,
                action="Vente unité QR",
                type_entite="unite_produit",
                entite_id=unite.id,
                details=f"Unité {unite.tracabilite} vendue via commande {commande.id}"
            )

    commande.total_ht = total_ht
    commande.tva = 0.18 * total_ht if data.tva_appliquee else 0
    commande.total_ttc = total_ht + commande.tva

    db.commit()
    db.refresh(commande)
    
    log_action(
        db=db,
        current_user=current_user,
        action=" Vente Effectuer",
        type_entite="commande_vente",
        entite_id=commande.id,
        details=f"Commande #{commande.id} pour Client {client.nom} — Total TTC: {commande.total_ttc:.2f} €"
    )

    generate_facture_from_commande(db, commande, "vente")
    facture = generate_facture_from_commande(db, commande, "vente")
    pdf_path = generate_facture_pdf(facture)
    filename = os.path.basename(pdf_path)

    return {"message": "Commande vente creee", "commande_id": commande.id, "facture": filename}

# ➕ Créer une commande achat
@router_achats.post("/")
def create_commande_achat(
    data: CommandeAchatCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == data.fournisseur_id,
        Fournisseur.user_id == parent_user_id
    ).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")

    commande = CommandeAchat(
        fournisseur_id=data.fournisseur_id,
        tva_appliquee=data.tva_appliquee,
        user_id=current_user.id  # 🔐 Liaison sécurisée
    )
    db.add(commande)
    db.commit()
    db.refresh(commande)

    total_ht = 0
    for ligne_data in data.lignes:
        produit = db.query(Produit).filter(
            Produit.id == ligne_data.produit_id,
            Produit.user_id == parent_user_id
        ).first()
        if not produit:
            raise HTTPException(status_code=400, detail=f"Produit non trouvé")

        produit.quantite += ligne_data.quantite
        total_ligne = produit.prix_achat * ligne_data.quantite
        total_ht += total_ligne

        db.add(LigneCommandeAchat(
            commande_id=commande.id,
            produit_id=produit.id,
            description=produit.nom,
            quantite=ligne_data.quantite,
            prix_unitaire=produit.prix_achat,
            total_ligne=total_ligne
        ))

    commande.total_ht = total_ht
    commande.tva = 0.18 * total_ht if data.tva_appliquee else 0
    commande.total_ttc = total_ht + commande.tva

    db.commit()
    db.refresh(commande)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Création  achat",
        type_entite="commande_achat",
        entite_id=commande.id,
        details=f"Commande #{commande.id} pour fournisseur {fournisseur.nom} — Total TTC: {commande.total_ttc:.2f} €"
    )


    generate_facture_from_commande(db, commande, "achat")

    return {"message": "Commande achat creee", "commande_id": commande.id}

# 📋 Lister les commandes ventes
@router_ventes.get("/")
def get_commandes_ventes(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(CommandeVente).filter(CommandeVente.user_id == parent_user_id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeVente.date_commande >= date_start)
    return query.all()

# 🔍 Détail d'une commande vente
@router_ventes.get("/{commande_id}")
def get_commande_vente(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    commande = db.query(CommandeVente).filter(
        CommandeVente.id == commande_id,
        CommandeVente.user_id == parent_user_id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande vente non trouvée")
    return commande

# 📋 Lister les commandes achats
@router_achats.get("/")
def get_commandes_achats(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):  
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(CommandeAchat).filter(CommandeAchat.user_id == parent_user_id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeAchat.date_commande >= date_start)
    return query.all()

# 🔍 Détail d'une commande achat
@router_achats.get("/{commande_id}")
def get_commande_achat(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    commande = db.query(CommandeAchat).filter(
        CommandeAchat.id == commande_id,
        CommandeAchat.user_id == parent_user_id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande achat non trouvée")
    return commande
