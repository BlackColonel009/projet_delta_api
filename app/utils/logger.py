from sqlalchemy.orm import Session
from typing import Optional
from app.models.model_historique_general import Historique

def log_action(
    db: Session,
    action: str,
    type_entite: str,
    entite_id: Optional[int] = None,
    current_user=None,
    details: Optional[str] = None
):
    """
    📦 Enregistre une action dans l'historique général.
    - user_id = toujours le main_user (pour filtrage par groupe)
    - sub_user_id = optionnel (si action faite par un sub-user)
    """
    if not current_user:
        return  # sécurité

    if getattr(current_user, "is_main_user", False):
        user_id = current_user.id
        sub_user_id = None
    else:
        user_id = current_user.parent_user_id
        sub_user_id = current_user.id

    h = Historique(
        action=action,
        type_entite=type_entite,
        entite_id=entite_id,
        user_id=user_id,
        sub_user_id=sub_user_id,
        details=details
    )
    db.add(h)
    db.commit()
