# 📦 ROUTES POUR Commande Vente et Achat

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timedelta
from typing import Optional
from app.database import get_db
from app.models.model_categorie import Categorie
from app.models.model_client_produit import ClientProduit
from app.models.model_clientfollowup import ClientFollowup, FollowupStatus
from app.models.model_produit import Produit
from app.models.model_client import Client
from app.models.model_fournisseur import Fournisseur
from app.models.model_commande import CommandeVente, LigneCommandeVente, CommandeAchat, LigneCommandeAchat
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from app.services.generate_facture_from_commande import generate_facture_from_commande, generate_facture_pdf
from app.services.traceability_service import create_generated_unit
from app.schemas.commande_schema import (
    CommandeAchatCreate,
    CommandeAchatOut,
    CommandeVenteCreate,
    CommandeVenteOut,
)
from app.utils.security import get_current_user
from app.utils.permissions import check_role
from app.schemas.user_schema import RoleEnum
from app.utils.logger import log_action
from app.utils.subscription_guard import (
    enforce_invoice_quota,
    resolve_subscription_access,
)
import os

router_ventes = APIRouter(prefix="/commandes-ventes", tags=["Commandes Ventes"])
router_achats = APIRouter(prefix="/commandes-achats", tags=["Commandes Achats"])


def _serialize_ligne_commande(ligne):
    """Conserve le nom historique même si la fiche produit a été supprimée."""
    produit = getattr(ligne, "produit", None)
    nom_produit = getattr(produit, "nom", None) or ligne.description
    return {
        "id": ligne.id,
        "produit_id": ligne.produit_id,
        "nom_produit": nom_produit or f"Produit #{ligne.produit_id}",
        "description": ligne.description,
        "quantite": ligne.quantite,
        "prix_unitaire": ligne.prix_unitaire,
        "total_ligne": ligne.total_ligne,
    }


def _serialize_commande_vente(commande):
    return {
        "id": commande.id,
        "client_id": commande.client_id,
        "date_commande": commande.date_commande,
        "total_ht": commande.total_ht,
        "total_ttc": commande.total_ttc,
        "tva": commande.tva,
        "tva_appliquee": commande.tva_appliquee,
        "statut": commande.statut,
        "lignes": [_serialize_ligne_commande(ligne) for ligne in commande.lignes],
    }


def _serialize_commande_achat(commande):
    return {
        "id": commande.id,
        "fournisseur_id": commande.fournisseur_id,
        "date_commande": commande.date_commande,
        "total_ht": commande.total_ht,
        "total_ttc": commande.total_ttc,
        "tva": commande.tva,
        "tva_appliquee": commande.tva_appliquee,
        "statut": commande.statut,
        "lignes": [_serialize_ligne_commande(ligne) for ligne in commande.lignes],
    }

# ➕ Créer une commande vente
@router_ventes.post("/")
def create_commande_vente(
    data: CommandeVenteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    # Détermine l'utilisateur principal (parent) s'il s'agit d'un sous-utilisateur
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    enforce_invoice_quota(db, current_user)
    subscription_access = resolve_subscription_access(db, current_user)

    # Vérifie que le client existe et appartient à l'utilisateur
    client = db.query(Client).filter(Client.id == data.client_id, Client.user_id == parent_user_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client non trouvé")

    categorie_nom = db.query(Categorie.nom).filter(Categorie.id == Produit.categorie_id).first()
    categorie_nom = categorie_nom[0] if categorie_nom else None


    
    # Crée la commande vente
    commande = CommandeVente(
        client_id=data.client_id,
        tva_appliquee=data.tva_appliquee,
        user_id=parent_user_id,
        statut = data.statut
    )
    db.add(commande)
    # L'ID est nécessaire pour rattacher les unités, mais la commande ne doit
    # être validée qu'après toutes les vérifications de stock.
    db.flush()
    db.refresh(commande)
    print("🧾 Statut reçu :", data.statut)


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



        prix_utilise = ligne_data.prix_unitaire if ligne_data.prix_unitaire is not None else produit.prix_vente
        total_ligne = prix_utilise * ligne_data.quantite
        total_ht += total_ligne

        # Crée la ligne de commande
        ligne_commande = LigneCommandeVente(
            commande_id=commande.id,
            produit_id=produit.id,
            description=produit.nom,
            quantite=ligne_data.quantite,
            prix_unitaire=prix_utilise,
            cout_achat_unitaire=float(produit.prix_achat or 0),
            total_ligne=total_ligne
        )
        db.add(ligne_commande)

        if data.statut == "en_attente":
            # Si des codes QR sont fournis, on les valide et on les marque comme vendus
            if ligne_data.codes:
                codes = list(dict.fromkeys(
                    code.strip() for code in ligne_data.codes if code and code.strip()
                ))
                if len(codes) != ligne_data.quantite:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Le nombre d'unités QR uniques doit correspondre "
                            "à la quantité vendue."
                        ),
                    )
                print("codes reçus:", codes)
                for code in codes:
                    unite = db.query(UniteProduit).filter(
                        UniteProduit.tracabilite == code,
                        UniteProduit.produit_id == produit.id,
                        UniteProduit.statut == "disponible"
                    ).with_for_update().first()
                    if not unite:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                f"L'unité {code} n'est plus disponible. "
                                "Elle est peut-être vendue, indisponible ou déjà en cours de vente."
                            ),
                        )
                    unite.statut = "en cours"
                    unite.commande_vente_id = commande.id
                    unite.date_modification = datetime.utcnow()

            # Si aucun code QR n’est fourni, affecte automatiquement les unités disponibles
            else:
                unites_dispo = db.query(UniteProduit).filter(
                    UniteProduit.produit_id == produit.id,
                    UniteProduit.statut == "disponible"
                ).with_for_update().limit(ligne_data.quantite).all()

                if len(unites_dispo) < ligne_data.quantite:
                    raise HTTPException(status_code=400, detail=f"Pas assez d'unités disponibles pour {produit.nom}")

                for unite in unites_dispo:
                    unite.statut = "en cours"
                    unite.commande_vente_id = commande.id
                    unite.date_modification = datetime.utcnow()
                    
            # 🔁 Mise à jour du stock disponible APRÈS modification des unités
            quantite_restante = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.statut == "disponible"
            ).count()
            produit.quantite = quantite_restante    
                
            # 🧠 Création d'un enregistrement ClientProduit
            client_produit = ClientProduit(
                client_id=client.id,
                commande_id=commande.id,
                produit_id=produit.id,
                nom_produit=produit.nom,
                categorie_produit=categorie_nom,
                prix_unitaire_backup=produit.prix_vente,
                quantite=ligne_data.quantite,
                prix_unitaire=prix_utilise,
                date_achat=commande.date_commande,
            )
            db.add(client_produit)
        
    

    # Calcul des totaux de la commande
    if not current_user.is_main_user:
        taux_tva = current_user.tva
    else:
        taux_tva = current_user.tva

    taux_tva = taux_tva or 0.0

    commande.total_ht = total_ht
    commande.tva = taux_tva * total_ht if data.tva_appliquee else 0
    commande.total_ttc = total_ht + commande.tva

    db.commit()

    date_achat = commande.date_commande or datetime.utcnow()

    # Déterminer le type de suivi selon le statut
    if data.statut == "validée":
        type_followup = "fidélisation"
    elif data.statut == "en_attente":
        type_followup = "relance_paiement"
    else:
        type_followup = None  # proforma, devis, etc. => pas de suivi

    if type_followup and subscription_access.has_feature("client_followup"):
        followup = ClientFollowup(
            user_id=parent_user_id,
            client_id=commande.client_id,
            commande_id=commande.id,
            date_achat=date_achat,
            statut=FollowupStatus.en_attente,
            date_prochain_envoi=datetime.utcnow() + timedelta(days=1),  # 2 minutes
            type_followup=type_followup
        )

        db.add(followup)
        db.commit()
        db.refresh(followup)

        log_action(
            db=db,
            current_user=current_user,
            action="Suivi client activé",
            type_entite="client_followup",
            entite_id=followup.id,
            details=f"Suivi {followup.type_followup} pour commande #{commande.id} du client {client.nom}"
        )


    db.refresh(commande)

    # Log d'action général de la commande
    log_action(
        db=db,
        current_user=current_user,
        action="Bordereau de vente ou de Livrable Effectuer",
        type_entite="commande_vente",
        entite_id=commande.id,
        details=f"Commande #{commande.id} pour Client {client.nom} — Total TTC: {commande.total_ttc:.2f} {current_user.devise}"
    )

    # Génération et exportation de la facture en PDF
    can_use_professional_invoice = subscription_access.has_feature(
        "professional_invoice"
    )
    facture = generate_facture_from_commande(
        db,
        commande,
        "vente",
        professional_invoice=can_use_professional_invoice,
    )
    filename = None
    if can_use_professional_invoice:
        tmp_path = generate_facture_pdf(facture, db)
        filename = os.path.basename(tmp_path)

    return {
        "message": "Commande vente creee",
        "commande_id": commande.id,
        "facture_id": facture.id,
        "facture": filename,
    }

# ➕ Créer une commande achat
@router_achats.post("/")
def create_commande_achat(
    data: CommandeAchatCreate,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    enforce_invoice_quota(db, current_user)
    fournisseur = db.query(Fournisseur).filter(
        Fournisseur.id == data.fournisseur_id,
        Fournisseur.user_id == parent_user_id
    ).first()
    if not fournisseur:
        raise HTTPException(status_code=404, detail="Fournisseur non trouvé")

    try:
        commande = CommandeAchat(
            fournisseur_id=data.fournisseur_id,
            tva_appliquee=data.tva_appliquee,
            user_id=parent_user_id,
            statut=data.statut,
        )
        db.add(commande)
        # L'ID est requis pour les lignes et les unités, sans valider une
        # commande partielle en base.
        db.flush()

        total_ht = 0.0
        for ligne_data in data.lignes:
            # Le verrou empêche deux achats simultanés de modifier le même
            # stock sans voir les changements de l'autre transaction.
            produit = db.query(Produit).filter(
                Produit.id == ligne_data.produit_id,
                Produit.user_id == parent_user_id,
                Produit.date_suppression.is_(None),
            ).with_for_update().first()
            if not produit:
                raise HTTPException(status_code=400, detail="Produit non trouvé")

            prix_utilise = (
                ligne_data.prix_unitaire
                if ligne_data.prix_unitaire is not None
                else produit.prix_achat
            )
            if prix_utilise is None or prix_utilise < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Prix d'achat invalide pour {produit.nom}",
                )

            total_ligne = prix_utilise * ligne_data.quantite
            total_ht += total_ligne
            produit.prix_achat = prix_utilise

            db.add(LigneCommandeAchat(
                commande_id=commande.id,
                produit_id=produit.id,
                description=produit.nom,
                quantite=ligne_data.quantite,
                prix_unitaire=prix_utilise,
                total_ligne=total_ligne,
            ))

            for _ in range(ligne_data.quantite):
                create_generated_unit(
                    db,
                    produit_id=produit.id,
                    suffix=fournisseur.nom,
                    commande_achat_id=commande.id,
                )

            # La quantité affichée reste dérivée des unités réellement
            # disponibles, même après une suppression définitive du stock.
            produit.quantite = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.statut == "disponible",
            ).count()

        taux_tva = (
            current_user.main_user.tva
            if not current_user.is_main_user
            else current_user.tva
        ) or 0.0
        commande.total_ht = total_ht
        commande.tva = taux_tva * total_ht if data.tva_appliquee else 0
        commande.total_ttc = total_ht + commande.tva

        # Une seule validation : commande, lignes, stock et unités réussissent
        # ensemble ou sont tous annulés.
        db.commit()
        db.refresh(commande)
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="L'achat n'a pas pu être enregistré. Aucune modification partielle n'a été conservée.",
        ) from error

    
    log_action(
        db=db,
        current_user=current_user,
        action="Création  achat",
        type_entite="commande_achat",
        entite_id=commande.id,
        details=f"Commande #{commande.id} pour fournisseur {fournisseur.nom} — Total TTC: {commande.total_ttc:.2f} €"
    )


    access = resolve_subscription_access(db, current_user)
    generate_facture_from_commande(
        db,
        commande,
        "achat",
        professional_invoice=access.has_feature("professional_invoice"),
    )

    return {"message": "Commande achat creee", "commande_id": commande.id}

# 📋 Lister les commandes ventes
@router_ventes.get("/", response_model=list[CommandeVenteOut])
def get_commandes_ventes(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(CommandeVente).options(
        selectinload(CommandeVente.lignes).selectinload(LigneCommandeVente.produit)
    ).filter(CommandeVente.user_id == parent_user_id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeVente.date_commande >= date_start)
    return [_serialize_commande_vente(commande) for commande in query.all()]

# 🔍 Détail d'une commande vente
@router_ventes.get("/{commande_id}", response_model=CommandeVenteOut)
def get_commande_vente(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier,  RoleEnum.commercial, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    commande = db.query(CommandeVente).options(
        selectinload(CommandeVente.lignes).selectinload(LigneCommandeVente.produit)
    ).filter(
        CommandeVente.id == commande_id,
        CommandeVente.user_id == parent_user_id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande vente non trouvée")
    return _serialize_commande_vente(commande)

# 📋 Lister les commandes achats
@router_achats.get("/", response_model=list[CommandeAchatOut])
def get_commandes_achats(
    start: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):  
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    query = db.query(CommandeAchat).options(
        selectinload(CommandeAchat.lignes).selectinload(LigneCommandeAchat.produit)
    ).filter(CommandeAchat.user_id == parent_user_id)
    if start:
        date_start = datetime.strptime(start, "%Y-%m-%d").date()
        query = query.filter(CommandeAchat.date_commande >= date_start)
    return [_serialize_commande_achat(commande) for commande in query.all()]

# 🔍 Détail d'une commande achat
@router_achats.get("/{commande_id}", response_model=CommandeAchatOut)
def get_commande_achat(
    commande_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin,  RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    commande = db.query(CommandeAchat).options(
        selectinload(CommandeAchat.lignes).selectinload(LigneCommandeAchat.produit)
    ).filter(
        CommandeAchat.id == commande_id,
        CommandeAchat.user_id == parent_user_id
    ).first()
    if not commande:
        raise HTTPException(status_code=404, detail="Commande achat non trouvée")
    return _serialize_commande_achat(commande)
