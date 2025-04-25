# 📚 LOGIQUE D'ENREGISTREMENT DANS L'HISTORIQUE GÉNÉRAL
# Fichier : app/utils/logger.py

from app.models.model_historique_general import Historique
from sqlalchemy.orm import Session
from typing import Optional

def log_action(
    db: Session,
    action: str,
    type_entite: str,
    entite_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[str] = None
):
    """
    📦 Enregistre une action dans l'historique général
    """
    historique = Historique(
        action=action,
        type_entite=type_entite,
        entite_id=entite_id,
        user_id=user_id,
        details=details
    )
    db.add(historique)
    db.commit()
