"""Immutable presentation and issuer data captured when an invoice is created."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.model_enterprise import Enterprise
from app.models.model_user import SubUser, User


DEFAULT_COLOR = "#5C6BC0"
DEFAULT_SIMPLE_TEMPLATE = "simple_classic"
DEFAULT_PROFESSIONAL_TEMPLATE = "professional_signature"


def validate_official_invoice_date(value: datetime | None) -> datetime:
    """Return the official document date while keeping creation time separate."""
    now = datetime.utcnow()
    if value is None:
        return now
    normalized = (
        value.astimezone(timezone.utc).replace(tzinfo=None)
        if value.tzinfo
        else value
    )
    if normalized > now.replace(microsecond=0):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INVOICE_DATE",
                "message": "La date de facture ne peut pas être dans le futur.",
            },
        )
    if normalized.year < 2000:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INVOICE_DATE",
                "message": "La date de facture sélectionnée est invalide.",
            },
        )
    return normalized


def invoice_snapshot_values(
    db: Session,
    actor,
    enterprise_id: int,
) -> dict:
    enterprise = db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()
    owner = None
    if isinstance(actor, SubUser):
        owner = db.query(User).filter(User.id == actor.parent_user_id).first()
        issuer_name = actor.username
        issuer_role = actor.role
        issued_by_user_id = None
        issued_by_sub_user_id = actor.id
    else:
        owner = actor
        issuer_name = (
            getattr(actor, "username", None)
            or getattr(actor, "email", None)
            or "Administrateur"
        )
        issuer_role = "Propriétaire"
        issued_by_user_id = getattr(actor, "id", None)
        issued_by_sub_user_id = None

    return {
        "issued_by_user_id": issued_by_user_id,
        "issued_by_sub_user_id": issued_by_sub_user_id,
        "issuer_name_snapshot": issuer_name,
        "issuer_role_snapshot": issuer_role,
        "invoice_color_snapshot": (
            getattr(enterprise, "invoice_color", None)
            or getattr(owner, "facture_color", None)
            or DEFAULT_COLOR
        ),
        "simple_template_snapshot": (
            getattr(enterprise, "simple_invoice_template", None)
            or DEFAULT_SIMPLE_TEMPLATE
        ),
        "professional_template_snapshot": (
            getattr(enterprise, "professional_invoice_template", None)
            or DEFAULT_PROFESSIONAL_TEMPLATE
        ),
    }
