from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


REUSABLE_UNIT_STATUSES = {
    "indisponible",
    "supprime",
    "supprimé",
    "deleted",
}
TEMPORARY_UNIT_STATUSES = {"temp", "temporary"}


def _utcnow() -> datetime:
    # Les colonnes historiques sont naïves ; conserver ce format tout en
    # évitant datetime.utcnow(), désormais déprécié.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_unit_status(value: Optional[str]) -> str:
    return (value or "").strip().lower()


@dataclass(frozen=True)
class UnitAttachmentResult:
    action: str
    previous_product_id: Optional[int] = None
    previous_product_name: Optional[str] = None

    @property
    def was_added(self) -> bool:
        return self.action in {"attached", "reactivated", "moved"}


def attach_reusable_unit(
    unit,
    target_product,
    *,
    enterprise_id: int,
    now: Optional[datetime] = None,
) -> UnitAttachmentResult:
    """Rattache une unité temporaire ou supprimée sans toucher aux ventes.

    Une suppression de stock est logique : l'unité reste dans la même ligne
    afin de préserver son historique. Elle peut ensuite être réactivée sur la
    même fiche ou déplacée vers une autre fiche de la même entreprise.
    """

    now = now or _utcnow()
    status = normalize_unit_status(getattr(unit, "statut", None))
    target_product_id = int(target_product.id)
    unit_enterprise_id = getattr(unit, "enterprise_id", None)

    # Une unité ne doit jamais traverser silencieusement deux entreprises.
    if unit_enterprise_id not in (None, enterprise_id):
        return UnitAttachmentResult("conflict")

    previous_product_id = getattr(unit, "produit_id", None)
    previous_product = getattr(unit, "produit", None)
    previous_product_name = getattr(previous_product, "nom", None)

    if previous_product_id == target_product_id:
        if status in REUSABLE_UNIT_STATUSES:
            unit.statut = "disponible"
            unit.enterprise_id = enterprise_id
            unit.date_modification = now
            return UnitAttachmentResult(
                "reactivated",
                previous_product_id=previous_product_id,
                previous_product_name=previous_product_name,
            )
        return UnitAttachmentResult("already_linked")

    if previous_product_id is None and (
        status in TEMPORARY_UNIT_STATUSES or status in REUSABLE_UNIT_STATUSES
    ):
        unit.produit_id = target_product_id
        unit.enterprise_id = enterprise_id
        unit.statut = "disponible"
        if status in TEMPORARY_UNIT_STATUSES:
            unit.date_creation = now
        unit.date_modification = now
        return UnitAttachmentResult("attached")

    if status in REUSABLE_UNIT_STATUSES:
        unit.produit_id = target_product_id
        unit.enterprise_id = enterprise_id
        unit.statut = "disponible"
        unit.date_modification = now
        # Une unité supprimée n'est pas liée à une vente active. Cette remise à
        # zéro défensive évite qu'une ancienne relation incohérente la bloque.
        if hasattr(unit, "commande_vente_id"):
            unit.commande_vente_id = None
        return UnitAttachmentResult(
            "moved",
            previous_product_id=previous_product_id,
            previous_product_name=previous_product_name,
        )

    # Disponible sur une autre fiche, vendue ou en cours : conflit protégé.
    return UnitAttachmentResult("conflict")


def refresh_available_product_quantity(db, product_id: Optional[int]) -> int:
    if product_id is None:
        return 0
    # Imports locaux pour garder ce service indépendant des routes.
    from app.models.model_produit import Produit
    from app.models.model_unite_produit import UniteProduit

    quantity = (
        db.query(UniteProduit)
        .filter(
            UniteProduit.produit_id == product_id,
            UniteProduit.statut == "disponible",
        )
        .count()
    )
    product = db.query(Produit).filter(Produit.id == product_id).first()
    if product is not None:
        product.quantite = quantity
        product.date_modification = _utcnow()
    return quantity
