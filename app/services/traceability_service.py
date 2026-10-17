import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.model_unite_produit import UniteProduit


def _safe_suffix(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    normalized = normalized.strip("_")[:48]
    return f"-{normalized}" if normalized else ""


def create_generated_unit(
    db: Session,
    *,
    produit_id: int,
    statut: str = "disponible",
    suffix: Optional[str] = None,
    date_creation: Optional[datetime] = None,
    commande_achat_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
) -> UniteProduit:
    """Crée une traçabilité qui ne dépend jamais du nombre d'unités restantes.

    L'identifiant SQL est fourni par la séquence de la base et n'est pas
    réutilisé après une suppression. Une valeur temporaire UUID permet de
    respecter la contrainte UNIQUE pendant le premier flush.
    """
    if enterprise_id is None:
        from app.models.model_produit import Produit

        enterprise_id = db.query(Produit.enterprise_id).filter(
            Produit.id == produit_id
        ).scalar()
    unit = UniteProduit(
        produit_id=produit_id,
        enterprise_id=enterprise_id,
        tracabilite=f"TMP-{uuid4().hex}",
        statut=statut,
        date_creation=date_creation or datetime.utcnow(),
        commande_achat_id=commande_achat_id,
    )
    db.add(unit)
    db.flush()
    unit.tracabilite = (
        f"TRAC-{produit_id}-{unit.id:08d}{_safe_suffix(suffix)}"
    )
    return unit
