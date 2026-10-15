from datetime import datetime, timedelta
import secrets

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi_mail import FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session

from app.config import conf
from app.database import get_db
from app.models.model_reset_token import ResetToken
from app.models.model_user import User
from app.schemas.reset_schema import ResetCodeSchema
from app.services.account_cleanup_service import clear_company_operational_data
from app.utils.i18n import language_of, translated
from app.utils.logger import log_action
from app.utils.reset_token import generate_code, save_code, send_reset_email
from app.utils.security import hash_password, require_main_user


router = APIRouter(prefix="/reset", tags=["Réinitialisation"])
RESET_CODE_LIFETIME = timedelta(minutes=15)


def _valid_token(db: Session, user_id: int, code: str) -> ResetToken:
    token = (
        db.query(ResetToken)
        .filter(ResetToken.user_id == user_id, ResetToken.code == code)
        .order_by(ResetToken.created_at.desc(), ResetToken.id.desc())
        .first()
    )
    if not token or not token.created_at:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    if token.created_at < datetime.utcnow() - RESET_CODE_LIFETIME:
        db.delete(token)
        db.commit()
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    return token


@router.post("/request")
async def request_reset_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_user),
):
    """Send a short-lived code to the authenticated account owner."""
    code = str(100000 + secrets.randbelow(900000))
    try:
        db.query(ResetToken).filter(ResetToken.user_id == current_user.id).delete(
            synchronize_session=False
        )
        db.add(ResetToken(user_id=current_user.id, code=code))
        db.flush()

        language = language_of(current_user)
        message = MessageSchema(
            subject=translated(
                language,
                "Code de réinitialisation de votre compte",
                "Your account reset code",
            ),
            recipients=[current_user.email],
            body=translated(
                language,
                (
                    f"Bonjour {current_user.email},\n\n"
                    f"Voici votre code de réinitialisation : {code}\n"
                    "Ce code expire dans 15 minutes."
                ),
                (
                    f"Hello {current_user.email},\n\n"
                    f"Your account reset code is: {code}\n"
                    "This code expires in 15 minutes."
                ),
            ),
            subtype=MessageType.plain,
        )
        await FastMail(conf).send_message(message)
        db.commit()
    except Exception as error:
        db.rollback()
        print(f"Erreur d'envoi du code de réinitialisation {current_user.id}: {error}")
        raise HTTPException(
            status_code=502,
            detail="Le code n’a pas pu être envoyé. Réessayez dans un instant.",
        )
    return {"message": "Code de confirmation envoyé par email."}


@router.post("/verify")
def verify_reset_code(
    data: ResetCodeSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_main_user),
):
    """Clear operational company data after email-code confirmation."""
    _valid_token(db, current_user.id, data.code)
    try:
        clear_company_operational_data(db, current_user.id)
        db.query(ResetToken).filter(
            ResetToken.user_id == current_user.id
        ).delete(synchronize_session=False)
        log_action(
            db=db,
            current_user=current_user,
            action="Réinitialisation du compte",
            type_entite="utilisateur",
            entite_id=current_user.id,
            details=(
                "Suppression des données opérationnelles après validation "
                "du code envoyé par e-mail."
            ),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as error:
        db.rollback()
        print(f"Erreur de réinitialisation du compte {current_user.id}: {error}")
        raise HTTPException(
            status_code=500,
            detail="La réinitialisation a échoué. Aucune suppression partielle n’a été conservée.",
        )
    return {"message": "Votre compte a été réinitialisé avec succès."}


@router.post("/forgot-password")
def forgot_password(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email non trouvé")
    code = generate_code()
    save_code(db, user.id, code)
    send_reset_email(user.email, code, user.interface_language)
    return {"message": "Code envoyé à votre email"}


@router.post("/reset-password")
def reset_password(
    email: str = Body(...),
    code: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    token = _valid_token(db, user.id, code)
    user.password_hash = hash_password(new_password)
    db.delete(token)
    db.commit()
    return {"message": "Mot de passe réinitialisé avec succès"}
