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
from app.services.generate_facture_from_commande import generate_facture_from_commande
from app.schemas.commande_schema import CommandeVenteCreate, CommandeAchatCreate
from app.utils.security import get_current_user
from app.utils.permissions import check_role

router_ventes = APIRouter(prefix="/commandes-ventes", tags=["Commandes Ventes"])
router_achats = APIRouter(prefix="/commandes-achats", tags=["Commandes Achats"])

# ➕ Créer une commande vente
@router_ventes.post("/")
def create_commande_vente(
    data: CommandeVenteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "caissier", "commercial"]))
):
    client = db.query(Client).filter(Client.id == data.client_id, Client.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    commande = CommandeVente(
        client_id=data.client_id,
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
            Produit.user_id == current_user.id
        ).first()
        if not produit or produit.quantite < ligne_data.quantite:
            raise HTTPException(status_code=400, detail=f"Stock insuffisant pour {produit.nom}")

        produit.quantite -= ligne_data.quantite
        total_ligne = produit.prix_vente * ligne_data.quantite
        total_ht += total_ligne

        db.add(LigneCommandeVente(
            commande_id=commande.id,
            produit_id=produit.id,
            description=produit.nom,
            quantite=ligne_data.quantite,
            prix_unitaire=produit.prix_vente,
            total_ligne=total_ligne
        ))

    commande.total_ht = total_ht
    commande.tva = 0.18 * total_ht if data.tva_appliquee else 0
    commande.total_ttc = total_ht + commande.tva

    db.commit()
    db.refresh(commande)

    generate_facture_from_commande(db, commande, "vente")

    return {"message": "Commande vente créée", "commande_id": commande.id}

# ➕ Créer une commande achat
@router_achats.post("/")
def create_commande_achat(
    data: CommandeAchatCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "gestionnaire_stock", "caissier"]))
):
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == data.fournisseur_id,
        Fournisseur.user_id == current_user.id
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
            Produit.user_id == current_user.id
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

    generate_facture_from_commande(db, commande, "achat")

    return {"message": "Commande achat créée", "commande_id": commande.id}

# 📋 Lister les commandes ventes
@router_ventes.get("/")
def get_commandes_ventes(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "caissier", "commercial"]))
):
    query = db.query(CommandeVente).filter(CommandeVente.user_id == current_user.id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeVente.date_commande >= date_start)
    return query.all()

# 🔍 Détail d'une commande vente
@router_ventes.get("/{commande_id}")
def get_commande_vente(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "caissier", "commercial"]))
):
    commande = db.query(CommandeVente).filter(
        CommandeVente.id == commande_id,
        CommandeVente.user_id == current_user.id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande vente non trouvée")
    return commande

# 📋 Lister les commandes achats
@router_achats.get("/")
def get_commandes_achats(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "caissier", "gestionnaire_stock"]))
):
    query = db.query(CommandeAchat).filter(CommandeAchat.user_id == current_user.id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeAchat.date_commande >= date_start)
    return query.all()

# 🔍 Détail d'une commande achat
@router_achats.get("/{commande_id}")
def get_commande_achat(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role(["admin", "caissier", "gestionnaire_stock"]))
):
    commande = db.query(CommandeAchat).filter(
        CommandeAchat.id == commande_id,
        CommandeAchat.user_id == current_user.id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande achat non trouvée")
    return commande
