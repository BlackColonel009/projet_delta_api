from sqlalchemy.orm import Session
from typing import Optional
from app.models.model_historique_general import Historique
from app.models.model_user import SubUser, User

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
        nom_user = getattr(current_user, "email", None)
        nom_sub_user = None
    else:
        sub_user = db.query(SubUser).filter(SubUser.id == current_user.id).first()
        parent_user = db.query(User).filter(User.id == sub_user.parent_user_id).first()

        user_id = parent_user.id
        sub_user_id = sub_user.id
        nom_user = parent_user.email
        nom_sub_user = sub_user.username

    h = Historique(
        action=action,
        type_entite=type_entite,
        entite_id=entite_id,
        user_id=user_id,
        sub_user_id=sub_user_id,
        details=details,
        nom_user=nom_user,
        nom_sub_user=nom_sub_user,
    )
    db.add(h)
    db.commit()
