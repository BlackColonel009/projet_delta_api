"""Transactional cleanup helpers for owner accounts."""

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.models.model_categorie import Categorie
from app.models.model_client import Client
from app.models.model_client_produit import ClientProduit
from app.models.model_clientfollowup import ClientFollowup
from app.models.model_commande import (
    CommandeAchat,
    CommandeVente,
    LigneCommandeAchat,
    LigneCommandeVente,
)
from app.models.model_depense import Depense
from app.models.model_depot import Depot
from app.models.model_depot_service import DepotService
from app.models.model_depot_tarif import DepotTarif
from app.models.model_depot_tarif_items import DepotTarifItem
from app.models.model_facture import Facture, LigneFacture
from app.models.model_facture_depot import FactureDepot
from app.models.model_fournisseur import Fournisseur
from app.models.model_galerie import GaleriePhoto
from app.models.model_historique_general import Historique
from app.models.model_historique_intervention import HistoriqueIntervention
from app.models.model_intervention import Intervention, intervention_produits
from app.models.model_notification import Notification
from app.models.model_paiement import Paiement
from app.models.model_produit import Produit
from app.models.model_rapport import Rapport
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import SubUser


def clear_company_operational_data(db: Session, owner_id: int) -> None:
    """Delete company operations while keeping the owner and subscription."""
    client_ids = db.query(Client.id).filter(Client.user_id == owner_id)
    supplier_ids = db.query(Fournisseur.id).filter(Fournisseur.user_id == owner_id)
    product_ids = db.query(Produit.id).filter(Produit.user_id == owner_id)
    sale_ids = db.query(CommandeVente.id).filter(CommandeVente.user_id == owner_id)
    purchase_ids = db.query(CommandeAchat.id).filter(CommandeAchat.user_id == owner_id)
    invoice_ids = db.query(Facture.id).filter(
        or_(
            Facture.user_id == owner_id,
            Facture.client_id.in_(client_ids),
            Facture.fournisseur_id.in_(supplier_ids),
        )
    )
    depot_ids = db.query(Depot.id).filter(Depot.user_id == owner_id)
    intervention_ids = db.query(Intervention.id).filter(
        Intervention.user_id == owner_id
    )
    sub_user_ids = db.query(SubUser.id).filter(SubUser.parent_user_id == owner_id)

    db.query(Paiement).filter(
        or_(Paiement.user_id == owner_id, Paiement.facture_id.in_(invoice_ids))
    ).delete(synchronize_session=False)
    db.query(LigneFacture).filter(
        or_(LigneFacture.user_id == owner_id, LigneFacture.facture_id.in_(invoice_ids))
    ).delete(synchronize_session=False)
    db.query(Facture).filter(Facture.id.in_(invoice_ids)).delete(
        synchronize_session=False
    )

    db.query(FactureDepot).filter(FactureDepot.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(DepotTarifItem).filter(DepotTarifItem.depot_id.in_(depot_ids)).delete(
        synchronize_session=False
    )
    db.query(Depot).filter(Depot.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(DepotTarif).filter(DepotTarif.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(DepotService).filter(DepotService.user_id == owner_id).delete(
        synchronize_session=False
    )

    db.query(ClientFollowup).filter(ClientFollowup.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(ClientProduit).filter(ClientProduit.client_id.in_(client_ids)).delete(
        synchronize_session=False
    )
    db.query(UniteProduit).filter(
        or_(
            UniteProduit.produit_id.in_(product_ids),
            UniteProduit.commande_vente_id.in_(sale_ids),
            UniteProduit.commande_achat_id.in_(purchase_ids),
        )
    ).delete(synchronize_session=False)
    db.query(LigneCommandeVente).filter(
        or_(
            LigneCommandeVente.user_id == owner_id,
            LigneCommandeVente.commande_id.in_(sale_ids),
        )
    ).delete(synchronize_session=False)
    db.query(LigneCommandeAchat).filter(
        or_(
            LigneCommandeAchat.user_id == owner_id,
            LigneCommandeAchat.commande_id.in_(purchase_ids),
        )
    ).delete(synchronize_session=False)
    db.query(CommandeVente).filter(CommandeVente.id.in_(sale_ids)).delete(
        synchronize_session=False
    )
    db.query(CommandeAchat).filter(CommandeAchat.id.in_(purchase_ids)).delete(
        synchronize_session=False
    )

    db.query(HistoriqueIntervention).filter(
        or_(
            HistoriqueIntervention.user_id == owner_id,
            HistoriqueIntervention.sub_user_id.in_(sub_user_ids),
            HistoriqueIntervention.intervention_id.in_(intervention_ids),
        )
    ).delete(synchronize_session=False)
    db.execute(
        delete(intervention_produits).where(
            intervention_produits.c.intervention_id.in_(intervention_ids)
        )
    )
    db.query(Intervention).filter(Intervention.id.in_(intervention_ids)).delete(
        synchronize_session=False
    )

    db.query(GaleriePhoto).filter(GaleriePhoto.produit_id.in_(product_ids)).delete(
        synchronize_session=False
    )
    db.query(Historique).filter(
        or_(
            Historique.user_id == owner_id,
            Historique.sub_user_id.in_(sub_user_ids),
        )
    ).delete(synchronize_session=False)
    db.query(Notification).filter(
        or_(
            Notification.parent_user_id == owner_id,
            Notification.sub_user_id.in_(sub_user_ids),
        )
    ).delete(synchronize_session=False)
    db.query(Depense).filter(Depense.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(Rapport).filter(
        or_(Rapport.user_id == owner_id, Rapport.sub_user_id.in_(sub_user_ids))
    ).delete(synchronize_session=False)
    db.query(Produit).filter(Produit.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(Client).filter(Client.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(Fournisseur).filter(Fournisseur.user_id == owner_id).delete(
        synchronize_session=False
    )
    db.query(Categorie).filter(Categorie.user_id == owner_id).delete(
        synchronize_session=False
    )
