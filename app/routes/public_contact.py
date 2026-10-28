"""Contact vitrine : réutilise SMTP, destinataire fixé côté serveur."""
import asyncio
import logging
from collections import OrderedDict, deque
from html import escape
from time import monotonic
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import settings
from app.core.mail import send_email_message

router = APIRouter(prefix="/public", tags=["Contact public"])
logger = logging.getLogger(__name__)


class ContactMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    company: str = Field(default="", max_length=160)
    business: str = Field(min_length=2, max_length=100)
    plan: str = Field(default="À définir ensemble", max_length=80)
    billing_cycle: Literal["monthly", "annual", "unspecified"] = "unspecified"
    message: str = Field(min_length=10, max_length=5000)
    consent: Literal[True]
    website: str = Field(default="", max_length=200)

    @field_validator("name", "company", "business", "plan")
    @classmethod
    def single_line(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("Une seule ligne est autorisée")
        return value


class ContactRateLimit:
    """Limites par processus ; compléter au proxy pour plusieurs workers.

    Aucun en-tête X-Forwarded-For fourni par le visiteur n'est utilisé.
    """
    def __init__(self):
        self.clients = OrderedDict()
        self.total = deque()
        self.lock = asyncio.Lock()

    async def check(self, address):
        async with self.lock:
            now = monotonic()
            while self.total and self.total[0] <= now - 3600:
                self.total.popleft()
            attempts = self.clients.pop(address, deque())
            while attempts and attempts[0] <= now - 600:
                attempts.popleft()
            self.clients[address] = attempts
            while len(self.clients) > 4096:
                self.clients.popitem(last=False)
            if len(attempts) >= 3 or len(self.total) >= 60:
                raise HTTPException(429, "Trop de demandes. Réessayez plus tard.", headers={"Retry-After": "600"})
            attempts.append(now)
            self.total.append(now)


rate_limit = ContactRateLimit()


@router.get("/contact")
async def availability():
    return {"available": bool(settings.MAIL_ENABLED and settings.CONTACT_EMAIL)}


@router.post("/contact")
async def contact(payload: ContactMessage, request: Request):
    await rate_limit.check(request.client.host if request.client else "unknown")
    if payload.website:
        raise HTTPException(400, "Demande invalide.")
    if not settings.MAIL_ENABLED or not settings.CONTACT_EMAIL:
        raise HTTPException(503, "Le formulaire est momentanément indisponible.")
    reference = uuid4().hex[:12]
    cycle = {"monthly": "Mensuelle", "annual": "Annuelle", "unspecified": "À préciser"}[payload.billing_cycle]
    fields = [("Référence", reference), ("Nom", payload.name), ("E-mail", str(payload.email)),
              ("Entreprise", payload.company or "Non précisée"), ("Activité", payload.business),
              ("Offre souhaitée", payload.plan), ("Facturation", cycle)]
    rows = "".join(f"<tr><th align='left' style='padding:8px'>{escape(k)}</th><td style='padding:8px'>{escape(v)}</td></tr>" for k, v in fields)
    message = escape(payload.message).replace("\n", "<br>")
    body = f"<html lang='fr'><body style='font-family:Arial,sans-serif;color:#241a29'><h1 style='color:#7a2cbf'>Trade Care</h1><h2>Nouvelle demande depuis le site vitrine</h2><table>{rows}</table><h3>Message</h3><p>{message}</p><p>Le visiteur a accepté d’être recontacté au sujet de cette demande.</p></body></html>"
    try:
        sent = await send_email_message(to_email=settings.CONTACT_EMAIL,
            subject=f"Trade Care — Demande site vitrine [{reference}]", body=body,
            reply_to=str(payload.email), is_html=True)
    except Exception:
        logger.error("Échec du contact vitrine, référence %s", reference)
        sent = False
    if not sent:
        raise HTTPException(503, "L’envoi n’a pas pu être confirmé. Contactez-nous par e-mail ou WhatsApp.")
    return {"status": "sent", "reference": reference}
