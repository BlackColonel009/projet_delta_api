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
from app.models.model_unite_produit import UniteProduit
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
    # Détermine l'utilisateur principal (parent) s'il s'agit d'un sous-utilisateur
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    # Vérifie que le client existe et appartient à l'utilisateur
    client = db.query(Client).filter(Client.id == data.client_id, Client.user_id == parent_user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    # Crée la commande vente
    commande = CommandeVente(
        client_id=data.client_id,
        tva_appliquee=data.tva_appliquee,
        user_id=parent_user_id
    )
    db.add(commande)
    db.commit()
    db.refresh(commande)

    total_ht = 0

    # Traite chaque ligne de commande
    for ligne_data in data.lignes:
        produit = db.query(Produit).filter(
            Produit.id == ligne_data.produit_id,
            Produit.user_id == parent_user_id
        ).first()

        if not produit:
            raise HTTPException(status_code=404, detail=f"Produit introuvable pour l'ID {ligne_data.produit_id}")

        if produit.quantite < ligne_data.quantite:
            raise HTTPException(status_code=400, detail=f"Stock insuffisant pour {produit.nom} Contactez vite votre fournisseur!")

        # Décrémente le stock
        produit.quantite -= ligne_data.quantite
        total_ligne = produit.prix_vente * ligne_data.quantite
        total_ht += total_ligne

        # Crée la ligne de commande
        ligne_commande = LigneCommandeVente(
            commande_id=commande.id,
            produit_id=produit.id,
            description=produit.nom,
            quantite=ligne_data.quantite,
            prix_unitaire = ligne_data.prix_unitaire if ligne_data.prix_unitaire is not None else produit.prix_vente,
            total_ligne=total_ligne
        )
        db.add(ligne_commande)

        # Si des codes QR sont fournis, on les valide et on les marque comme vendus
        if ligne_data.codes:
            for code in ligne_data.codes:
                unite = db.query(UniteProduit).filter(
                    UniteProduit.tracabilite == code,
                    UniteProduit.produit_id == produit.id,
                    UniteProduit.statut == "disponible"
                ).first()
                if not unite:
                    raise HTTPException(status_code=400, detail=f"Unité avec code {code} non trouvée ou déjà utilisée")
                unite.statut = "en cours"
                unite.commande_vente_id = commande.id
                unite.date_modification = datetime.utcnow()

        # Si aucun code QR n’est fourni, affecte automatiquement les unités disponibles
        else:
            unites_dispo = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.statut == "disponible"
            ).limit(ligne_data.quantite).all()

            if len(unites_dispo) < ligne_data.quantite:
                raise HTTPException(status_code=400, detail=f"Pas assez d'unités disponibles pour {produit.nom}")

            for unite in unites_dispo:
                unite.statut = "en cours"
                unite.commande_vente_id = commande.id
                unite.date_modification = datetime.utcnow()

    # Calcul des totaux de la commande
    commande.total_ht = total_ht
    commande.tva = 0.18 * total_ht if data.tva_appliquee else 0
    commande.total_ttc = total_ht + commande.tva

    db.commit()
    db.refresh(commande)

    # Log d'action général de la commande
    log_action(
        db=db,
        current_user=current_user,
        action="Vente Effectuer",
        type_entite="commande_vente",
        entite_id=commande.id,
        details=f"Commande #{commande.id} pour Client {client.nom} — Total TTC: {commande.total_ttc:.2f} {current_user.devise}"
    )

    # Génération et exportation de la facture en PDF
    facture = generate_facture_from_commande(db, commande, "vente")
    tmp_path = generate_facture_pdf(facture)
    filename = os.path.basename(tmp_path)

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
        user_id=parent_user_id  # 🔐 Liaison sécurisée
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
        
        # ➕ Création automatique des unités QR
        for i in range(1, ligne_data.quantite + 1):
            qr_code = f"TRAC-{produit.id}-{str(i).zfill(4)}-Fournisseur_{fournisseur.nom}"

            unite = UniteProduit(
                produit_id=produit.id,
                tracabilite=qr_code,
                statut="disponible",
            )
            db.add(unite)

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
