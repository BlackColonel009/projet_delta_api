import asyncio
import logging

from fastapi_mail import FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from app.config import conf, settings


logger = logging.getLogger(__name__)

async def send_email_message(
    to_email: str,
    subject: str,
    body: str,
    reply_to: str = None,
    attachments: list = None,  # liste de chemins de fichiers
    is_html: bool = False,
) -> bool:
    if not settings.MAIL_ENABLED:
        logger.info("Envoi d'e-mail ignoré : MAIL_ENABLED=false")
        return False

    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.html if is_html else MessageType.plain,
        headers={"Reply-To": reply_to} if reply_to else None,
        attachments = attachments or []  # directement une liste de chemins (str)
    )

    # Une coupure SMTP ponctuelle (fréquente avec certains hébergeurs) ne doit
    # pas transformer l'action métier déjà validée en erreur HTTP 500.
    for attempt in range(2):
        try:
            await FastMail(conf).send_message(message)
            return True
        except (ConnectionErrors, OSError, TimeoutError) as error:
            logger.warning(
                "Échec SMTP vers %s (tentative %s/2): %s",
                to_email,
                attempt + 1,
                error,
            )
            if attempt == 0:
                await asyncio.sleep(1)

    logger.error("E-mail non envoyé à %s après deux tentatives.", to_email)
    return False
