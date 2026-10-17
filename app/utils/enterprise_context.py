from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_enterprise import Enterprise, EnterpriseMembership
from app.services.enterprise_service import (
    resolve_active_enterprise,
    resolve_default_enterprise,
)
from app.utils.security import get_active_user


@dataclass(frozen=True)
class ActiveEnterpriseContext:
    actor: object
    membership: EnterpriseMembership
    enterprise: Enterprise

    @property
    def group_id(self) -> int:
        return self.membership.group_id

    @property
    def enterprise_id(self) -> int:
        return self.enterprise.id


def get_active_enterprise_context(
    x_enterprise_id: int | None = Header(default=None, alias="X-Enterprise-ID"),
    current_user=Depends(get_active_user),
    db: Session = Depends(get_db),
) -> ActiveEnterpriseContext:
    """Résout l'entreprise de la requête et bloque toute usurpation de contexte.

    L'en-tête reste optionnel pendant la migration : l'entreprise principale est
    utilisée pour le propriétaire et l'entreprise assignée pour un collaborateur.
    """
    if x_enterprise_id is None:
        membership, enterprise = resolve_default_enterprise(db, current_user)
    else:
        membership, enterprise = resolve_active_enterprise(
            db,
            current_user,
            x_enterprise_id,
        )
    return ActiveEnterpriseContext(
        actor=current_user,
        membership=membership,
        enterprise=enterprise,
    )
