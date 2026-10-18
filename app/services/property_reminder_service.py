from datetime import datetime, timedelta

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text

from app.core.mail import send_email_message
from app.models.model_enterprise import Enterprise, EnterpriseGroup, EnterpriseServiceProfile
from app.models.model_notification import Notification
from app.models.model_property_rental import PropertyOccupancy, PropertyPaymentDue, PropertyReminderLog

DEFAULTS = {"enabled": True, "days_before": 3, "overdue_frequency_days": 3, "email_enabled": False}


def reminder_settings(db: Session, enterprise_id: int) -> dict:
    profile = db.query(EnterpriseServiceProfile).filter(EnterpriseServiceProfile.enterprise_id == enterprise_id, EnterpriseServiceProfile.service_code == "property_rental").first()
    stored = dict(profile.configuration_json or {}) if profile else {}
    return {**DEFAULTS, **stored.get("payment_reminders", {})}


def save_reminder_settings(db: Session, enterprise_id: int, values: dict) -> dict:
    profile = db.query(EnterpriseServiceProfile).filter(EnterpriseServiceProfile.enterprise_id == enterprise_id, EnterpriseServiceProfile.service_code == "property_rental").first()
    if not profile:
        profile = EnterpriseServiceProfile(enterprise_id=enterprise_id, service_code="property_rental", enabled=True, configuration_json={})
        db.add(profile)
    configuration = dict(profile.configuration_json or {})
    configuration["payment_reminders"] = {**DEFAULTS, **values}
    profile.configuration_json = configuration
    db.commit()
    return configuration["payment_reminders"]


def _key(due: PropertyPaymentDue, now: datetime, frequency: int) -> tuple[str, str]:
    days = (due.due_date.date() - now.date()).days
    if days >= 0:
        return f"upcoming:{due.due_date.date().isoformat()}", "upcoming"
    bucket = abs(days) // max(1, frequency)
    return f"overdue:{bucket}", "overdue"


def _html(enterprise, due, stage, remaining, days):
    title = "Échéance de loyer à venir" if stage == "upcoming" else "Rappel de loyer impayé"
    accent = getattr(enterprise, "invoice_color", None) or "#5C6BC0"
    return f"""<!doctype html><html><body style='margin:0;background:#f3f5f9;font-family:Arial,sans-serif;color:#202735'><table width='100%' cellpadding='0' cellspacing='0'><tr><td align='center' style='padding:28px 12px'><table width='620' style='max-width:620px;background:#fff;border-radius:18px;overflow:hidden'><tr><td style='background:{accent};padding:26px;color:#fff'><b style='font-size:13px'>{enterprise.name}</b><h1 style='margin:8px 0 0;font-size:24px'>{title}</h1></td></tr><tr><td style='padding:28px'><p>Bonjour {due.occupancy.client.nom},</p><p>Votre échéance pour <b>{due.occupancy.unit.name}</b> est {"prévue dans " + str(days) + " jour(s)" if stage == "upcoming" else "en retard de " + str(abs(days)) + " jour(s)"}.</p><table width='100%' style='background:#f7f8fb;border-radius:12px;padding:14px'><tr><td>Contrat</td><td align='right'><b>{due.occupancy.contract_number}</b></td></tr><tr><td>Date d'échéance</td><td align='right'><b>{due.due_date:%d/%m/%Y}</b></td></tr><tr><td>Reste à payer</td><td align='right'><b>{remaining:,.0f} {enterprise.currency}</b></td></tr></table><p style='margin-top:24px;color:#687084'>Ce message a été généré automatiquement par Trade Care pour {enterprise.name}.</p></td></tr></table></td></tr></table></body></html>"""


async def dispatch_property_reminders(db: Session, enterprise_id: int | None = None) -> dict:
    lock_acquired = True
    if db.bind and db.bind.dialect.name == "postgresql":
        lock_acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(834712)")).scalar())
    if not lock_acquired:
        return {"enterprises": 0, "notifications": 0, "emails": 0, "skipped": 0, "locked": True}
    now = datetime.utcnow()
    enterprises = db.query(Enterprise).filter(Enterprise.business_type == "property_rental", Enterprise.status == "active")
    if enterprise_id is not None:
        enterprises = enterprises.filter(Enterprise.id == enterprise_id)
    summary = {"enterprises": 0, "notifications": 0, "emails": 0, "skipped": 0}
    for enterprise in enterprises.all():
        settings = reminder_settings(db, enterprise.id)
        if not settings["enabled"]:
            continue
        summary["enterprises"] += 1
        group = db.query(EnterpriseGroup).filter(EnterpriseGroup.id == enterprise.group_id).first()
        cutoff = now + timedelta(days=max(0, int(settings["days_before"])))
        dues = db.query(PropertyPaymentDue).options(selectinload(PropertyPaymentDue.occupancy).selectinload(PropertyOccupancy.client), selectinload(PropertyPaymentDue.occupancy).selectinload(PropertyOccupancy.unit)).filter(PropertyPaymentDue.enterprise_id == enterprise.id, PropertyPaymentDue.status != "paid", PropertyPaymentDue.due_date <= cutoff).all()
        for due in dues:
            remaining = float(due.amount - due.paid_amount)
            if remaining <= 0:
                continue
            key, stage = _key(due, now, int(settings["overdue_frequency_days"]))
            days = (due.due_date.date() - now.date()).days
            exists = db.query(PropertyReminderLog.id).filter(PropertyReminderLog.due_id == due.id, PropertyReminderLog.channel == "internal", PropertyReminderLog.reminder_key == key).first()
            if not exists:
                db.add(Notification(titre="Loyer à venir" if stage == "upcoming" else "Loyer impayé", message=f"{due.occupancy.client.nom} · {due.occupancy.unit.name} · {remaining:,.0f} {enterprise.currency} · échéance {due.due_date:%d/%m/%Y}", parent_user_id=group.owner_user_id, enterprise_id=enterprise.id, is_read=False))
                db.add(PropertyReminderLog(enterprise_id=enterprise.id, due_id=due.id, channel="internal", reminder_key=key, status="sent"))
                db.commit(); summary["notifications"] += 1
            else:
                summary["skipped"] += 1
            email = getattr(due.occupancy.client, "email", None)
            if settings["email_enabled"] and email:
                sent_before = db.query(PropertyReminderLog.id).filter(PropertyReminderLog.due_id == due.id, PropertyReminderLog.channel == "email", PropertyReminderLog.reminder_key == key).first()
                if not sent_before:
                    sent = await send_email_message(to_email=email, subject=("Échéance de loyer" if stage == "upcoming" else "Rappel de loyer impayé") + f" — {enterprise.name}", body=_html(enterprise, due, stage, remaining, days), is_html=True)
                    db.add(PropertyReminderLog(enterprise_id=enterprise.id, due_id=due.id, channel="email", reminder_key=key, status="sent" if sent else "failed", error_message=None if sent else "SMTP indisponible"))
                    db.commit()
                    if sent: summary["emails"] += 1
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_unlock(834712)"))
    return summary
