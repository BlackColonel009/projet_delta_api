import random
from fastapi_mail import FastMail, MessageSchema, MessageType
from sqlalchemy.orm import Session
from app.models.model_reset_token import ResetToken
from app.config import conf

def generate_code() -> str:
    return str(random.randint(100000, 999999))


def save_code(db: Session, user_id: int, code: str):
    # Supprime les anciens codes existants
    db.query(ResetToken).filter(ResetToken.user_id == user_id).delete()

    token = ResetToken(user_id=user_id, code=code)
    db.add(token)
    db.commit()
    
def send_reset_email(email: str, code: str):
    message = MessageSchema(
        subject="Code de réinitialisation de votre mot de passe",
        recipients=[email],
        body=f"Voici votre code de réinitialisation : {code}",
        subtype=MessageType.plain
    )

    fm = FastMail(conf)
    import asyncio
    asyncio.run(fm.send_message(message))