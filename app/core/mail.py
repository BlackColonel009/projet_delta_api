import logging

from fastapi_mail import FastMail, MessageSchema, MessageType
from app.config import conf, settings


logger = logging.getLogger(__name__)

async def send_email_message(
    to_email: str,
    subject: str,
    body: str,
    reply_to: str = None,
    attachments: list = None  # liste de chemins de fichiers
) -> bool:
    if not settings.MAIL_ENABLED:
        logger.info("Envoi d'e-mail ignoré : MAIL_ENABLED=false")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.plain,
        headers={"Reply-To": reply_to} if reply_to else None,
        attachments = attachments or []  # directement une liste de chemins (str)
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    return True
