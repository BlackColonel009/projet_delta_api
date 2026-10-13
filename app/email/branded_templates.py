from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Iterable
from urllib.parse import quote

from app.config import settings
from app.utils.color_theme import build_document_palette
from app.utils.public_url import public_url
from app.utils.i18n import language_of, translated


def _tr(user, french: str, english: str) -> str:
    return translated(language_of(user), french, english)


def _text(value: object | None, fallback: str = "") -> str:
    return escape(str(value if value not in (None, "") else fallback))


def _money(value: float | int | None, currency: str) -> str:
    amount = float(value or 0)
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {_text(currency)}"


def _date(value: date | datetime | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def _company_identity(user) -> dict[str, str]:
    company = getattr(user, "societe_ou_entreprise", None) or _tr(
        user, "Votre entreprise", "Your company"
    )
    email = getattr(user, "email", None) or ""
    logo = public_url(getattr(user, "logo_entreprise", None))
    palette = build_document_palette(getattr(user, "facture_color", None))
    return {
        "company": _text(company),
        "email": _text(email),
        "email_raw": email,
        "logo": _text(logo),
        **palette,
    }


def _layout(
    *,
    user,
    preheader: str,
    eyebrow: str,
    title: str,
    introduction: str,
    content: str,
    badge: str | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    sender_name: str | None = None,
    contact_email: str | None = None,
    use_company_logo: bool = True,
    language_user=None,
) -> str:
    identity = _company_identity(user)
    language_user = language_user or user
    display_name = _text(sender_name) if sender_name else identity["company"]
    logo = (
        f'<img src="{identity["logo"]}" width="52" height="52" '
        'alt="Logo" style="display:block;width:52px;height:52px;object-fit:contain;'
        'border-radius:12px;background:#ffffff;padding:4px;border:0;">'
        if use_company_logo and identity["logo"]
        else '<div style="font-size:24px;font-weight:900;color:#ffffff;line-height:1;">TC</div>'
    )
    badge_html = (
        f'<span style="display:inline-block;padding:7px 11px;border-radius:999px;'
        f'background:{identity["primary_soft"]};color:{identity["primary_dark"]};'
        f'font-size:12px;font-weight:700;">{_text(badge)}</span>'
        if badge
        else ""
    )
    cta_html = (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin-top:24px;"><tr><td bgcolor="{identity["primary"]}" '
        f'style="border-radius:10px;"><a href="{_text(cta_url)}" '
        f'style="display:inline-block;padding:13px 20px;color:{identity["on_primary"]};'
        f'text-decoration:none;font-size:14px;font-weight:800;">{_text(cta_label)}</a>'
        f'</td></tr></table>'
        if cta_label and cta_url
        else ""
    )
    contact_email_raw = (
        contact_email if contact_email is not None else identity["email_raw"]
    )
    contact = (
        f'<a href="mailto:{_text(contact_email_raw)}" '
        f'style="color:{identity["primary"]};text-decoration:none;">'
        f'{_text(contact_email_raw)}</a>'
        if contact_email_raw
        else _tr(user, "votre interlocuteur habituel", "your usual contact")
    )
    footer_sender = (
        _tr(language_user, f"Communication envoyée par {display_name}.", f"Message sent by {display_name}.")
        if sender_name
        else _tr(
            language_user,
            f"Communication envoyée par {identity['company']} avec Trade Care.",
            f"Message sent by {identity['company']} with Trade Care.",
        )
    )

    return f"""<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f6f8;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{_text(preheader)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f6f8;">
    <tr><td align="center" style="padding:28px 12px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e5e7eb;">
        <tr><td style="padding:28px;background:{identity['primary_dark']};">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
            <tr>
              <td width="70" valign="middle">{logo}</td>
              <td valign="middle">
                <div style="font-size:11px;line-height:1.5;letter-spacing:1.6px;text-transform:uppercase;color:{identity['primary_soft']};font-weight:800;">{_text(eyebrow)}</div>
                <div style="margin-top:5px;font-size:22px;line-height:1.25;color:#ffffff;font-weight:900;">{display_name}</div>
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="height:5px;background:{identity['primary']};font-size:0;line-height:0;">&nbsp;</td></tr>
        <tr><td style="padding:30px 28px 18px;">
          {badge_html}
          <h1 style="margin:14px 0 10px;font-size:25px;line-height:1.25;color:#111827;">{_text(title)}</h1>
          <p style="margin:0;font-size:15px;line-height:1.7;color:#4b5563;">{_text(introduction)}</p>
        </td></tr>
        <tr><td style="padding:4px 28px 32px;">
          {content}
          {cta_html}
        </td></tr>
        <tr><td style="padding:22px 28px;background:{identity['primary_pale']};border-top:1px solid {identity['primary_soft']};">
          <p style="margin:0 0 7px;font-size:13px;line-height:1.55;color:#4b5563;">{_tr(language_user, 'Une question ? Répondez directement à cet email ou contactez', 'Any questions? Reply directly to this email or contact')} {contact}.</p>
          <p style="margin:0;font-size:11px;line-height:1.5;color:#6b7280;">{footer_sender}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def payment_reminder_email(
    *,
    user,
    client_name: str,
    order_id: int,
    product_names: Iterable[str],
    total: float,
    paid: float,
    balance: float,
    currency: str,
    order_date: date | datetime | None,
    delay_days: int,
) -> str:
    products = ", ".join(_text(name) for name in product_names) or _tr(user, "Aucun article renseigné", "No items provided")
    palette = _company_identity(user)
    rows = (
        (_tr(user, "Commande", "Order"), f"N° {_text(order_id)}"),
        (_tr(user, "Articles", "Items"), products),
        (_tr(user, "Date d’achat", "Purchase date"), _date(order_date)),
        (_tr(user, "Montant total", "Total amount"), _money(total, currency)),
        (_tr(user, "Déjà payé", "Already paid"), _money(paid, currency)),
    )
    details = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #edf0f2;color:#6b7280;font-size:13px;width:38%;">{label}</td>'
        f'<td style="padding:10px 0;border-bottom:1px solid #edf0f2;color:#111827;font-size:14px;font-weight:700;">{value}</td></tr>'
        for label, value in rows
    )
    content = f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">{details}</table>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:18px;background:{palette['primary_pale']};border:1px solid {palette['primary_soft']};border-radius:12px;">
        <tr><td style="padding:18px;">
          <div style="font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-weight:800;">{_tr(user, 'Reste à régler', 'Balance due')}</div>
          <div style="margin-top:5px;font-size:26px;color:{palette['primary_dark']};font-weight:900;">{_money(balance, currency)}</div>
        </td></tr>
      </table>
      <p style="margin:20px 0 0;font-size:14px;line-height:1.7;color:#4b5563;">{_tr(user, 'Si votre règlement a déjà été effectué, vous pouvez simplement ignorer ce message.', 'If you have already paid, you can simply ignore this message.')}</p>
    """
    email = getattr(user, "email", "") or ""
    return _layout(
        user=user,
        preheader=_tr(user, f"Rappel concernant la commande N° {order_id}", f"Reminder for order No. {order_id}"),
        eyebrow=_tr(user, "Suivi client", "Customer follow-up"),
        title=_tr(user, f"Bonjour {client_name}, votre règlement est en attente", f"Hello {client_name}, your payment is pending"),
        introduction=_tr(user, f"Le délai de paiement de {delay_days} jours accordé pour cette commande est arrivé à échéance.", f"The {delay_days}-day payment period for this order has expired."),
        content=content,
        badge=_tr(user, "Rappel de paiement", "Payment reminder"),
        cta_label=_tr(user, "Contacter l’entreprise", "Contact the company"),
        cta_url=f"mailto:{quote(email, safe='@')}?subject=Commande%20N%C2%B0%20{order_id}" if email else None,
    )


def loyalty_email(*, user, client_name: str, product_names: Iterable[str]) -> str:
    items = "".join(
        f'<tr><td width="24" valign="top" style="padding:7px 0;color:#16a34a;font-weight:900;">✓</td>'
        f'<td style="padding:7px 0;color:#374151;font-size:14px;">{_text(name)}</td></tr>'
        for name in product_names
    ) or f'<tr><td style="padding:7px 0;color:#374151;">{_tr(user, "Votre commande", "Your order")}</td></tr>'
    content = f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;background:#f9fafb;border-radius:12px;padding:12px 18px;">{items}</table>
      <p style="margin:20px 0 0;font-size:14px;line-height:1.7;color:#4b5563;">{_tr(user, 'Notre équipe reste disponible si vous avez besoin d’un conseil, d’une assistance ou d’un nouvel article.', 'Our team is available if you need advice, support or another item.')}</p>
    """
    email = getattr(user, "email", "") or ""
    return _layout(
        user=user,
        preheader=_tr(user, "Merci pour votre confiance.", "Thank you for your trust."),
        eyebrow=_tr(user, "Relation client", "Customer care"),
        title=_tr(user, f"Merci pour votre achat, {client_name}", f"Thank you for your purchase, {client_name}"),
        introduction=_tr(user, "Nous espérons que votre commande vous donne entière satisfaction.", "We hope you are completely satisfied with your order."),
        content=content,
        badge=_tr(user, "Merci pour votre confiance", "Thank you for your trust"),
        cta_label=_tr(user, "Écrire à notre équipe", "Contact our team"),
        cta_url=f"mailto:{quote(email, safe='@')}" if email else None,
    )


def product_recommendation_email(*, user, client_name: str, product) -> str:
    identity = _company_identity(user)
    image_url = public_url(getattr(product, "image_url", None))
    image = (
        f'<img src="{_text(image_url)}" width="180" alt="{_text(product.nom)}" '
        'style="display:block;width:100%;max-width:180px;height:150px;object-fit:cover;border-radius:12px;border:0;">'
        if image_url
        else f'<div style="width:180px;height:150px;border-radius:12px;background:{identity["primary_soft"]};text-align:center;line-height:150px;font-size:42px;">★</div>'
    )
    description = getattr(product, "caracteristiques", None) or getattr(product, "commentaire", None)
    price = getattr(product, "prix_vente", None)
    currency = getattr(user, "devise", "") or ""
    content = f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;background:#f9fafb;border:1px solid #edf0f2;border-radius:14px;">
        <tr>
          <td width="190" valign="top" style="padding:16px;">{image}</td>
          <td valign="top" style="padding:18px 18px 18px 0;">
            <div style="font-size:20px;line-height:1.3;color:#111827;font-weight:900;">{_text(product.nom)}</div>
            <div style="margin-top:8px;font-size:14px;line-height:1.6;color:#4b5563;">{_text(description, _tr(user, 'Un article sélectionné spécialement pour vous.', 'An item selected especially for you.'))}</div>
            <div style="margin-top:14px;font-size:18px;color:{identity['primary_dark']};font-weight:900;">{_money(price, currency)}</div>
          </td>
        </tr>
      </table>
      <p style="margin:18px 0 0;font-size:14px;line-height:1.7;color:#4b5563;">{_tr(user, 'La fiche complète de l’article est jointe à cet email au format PDF.', 'The full item sheet is attached to this email as a PDF.')}</p>
    """
    email = getattr(user, "email", "") or ""
    return _layout(
        user=user,
        preheader=_tr(user, f"Découvrez notre sélection : {getattr(product, 'nom', 'article')}", f"Discover our selection: {getattr(product, 'nom', 'item')}"),
        eyebrow=_tr(user, "Sélection personnalisée", "Selected for you"),
        title=_tr(user, f"{client_name}, cet article pourrait vous intéresser", f"{client_name}, you may be interested in this item"),
        introduction=_tr(user, "Nous avons sélectionné cette proposition en tenant compte de votre relation avec notre entreprise.", "We selected this offer based on your relationship with our company."),
        content=content,
        badge=_tr(user, "Notre recommandation", "Our recommendation"),
        cta_label=_tr(user, "Demander plus d’informations", "Request more information"),
        cta_url=f"mailto:{quote(email, safe='@')}?subject={quote('Information article ' + str(getattr(product, 'nom', '')))}" if email else None,
    )


def subscription_request_admin_email(*, requester, plan, request, recipient=None) -> str:
    recipient = recipient or requester
    cycle = _tr(
        recipient,
        "annuelle" if request.billing_cycle == "annual" else "mensuelle",
        "annual" if request.billing_cycle == "annual" else "monthly",
    )
    rows = (
        (_tr(recipient, "Entreprise", "Company"), _text(getattr(requester, "societe_ou_entreprise", None), _tr(recipient, "Non renseignée", "Not provided"))),
        ("Email", _text(getattr(requester, "email", None), _tr(recipient, "Non renseigné", "Not provided"))),
        (_tr(recipient, "Offre actuelle", "Current plan"), _text(request.current_plan_code, _tr(recipient, "Aucune", "None"))),
        (_tr(recipient, "Offre demandée", "Requested plan"), _text(getattr(plan, "name", None), request.requested_plan_code)),
        (_tr(recipient, "Facturation", "Billing"), cycle.capitalize()),
        (_tr(recipient, "Montant proposé", "Quoted amount"), _money(request.quoted_amount, request.currency)),
    )
    details = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #edf0f2;color:#6b7280;font-size:13px;width:38%;">{label}</td>'
        f'<td style="padding:10px 0;border-bottom:1px solid #edf0f2;color:#111827;font-size:14px;font-weight:700;">{value}</td></tr>'
        for label, value in rows
    )
    note = (
        f'<div style="margin-top:18px;padding:16px;border-radius:12px;background:#f9fafb;">'
        f'<div style="font-size:12px;color:#6b7280;font-weight:800;text-transform:uppercase;">{_tr(recipient, "Message de l’entreprise", "Company message")}</div>'
        f'<div style="margin-top:7px;font-size:14px;line-height:1.65;color:#374151;">{_text(request.note)}</div></div>'
        if request.note
        else ""
    )
    return _layout(
        user=requester,
        preheader=_tr(recipient, "Une entreprise souhaite changer d’offre Trade Care.", "A company would like to change its Trade Care plan."),
        eyebrow=_tr(recipient, "Abonnements Trade Care", "Trade Care subscriptions"),
        title=_tr(recipient, "Nouvelle demande de mise à niveau", "New upgrade request"),
        introduction=_tr(recipient, "Une demande nécessite votre validation dans l’espace Super Admin.", "A request requires your approval in the Super Admin area."),
        content=f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">{details}</table>{note}',
        badge=_tr(recipient, "Action requise", "Action required"),
        language_user=recipient,
    )


def subscription_request_decision_email(
    *,
    company,
    plan,
    request,
    approved: bool,
) -> str:
    status = _tr(company, "approuvée" if approved else "refusée", "approved" if approved else "declined")
    accent = "#15803d" if approved else "#b91c1c"
    cycle = _tr(company, "annuelle" if request.billing_cycle == "annual" else "mensuelle", "annual" if request.billing_cycle == "annual" else "monthly")
    response = (
        f'<div style="margin-top:18px;padding:16px;border-radius:12px;background:#f9fafb;">'
        f'<div style="font-size:12px;color:#6b7280;font-weight:800;text-transform:uppercase;">{_tr(company, "Réponse du Super Admin", "Super Admin response")}</div>'
        f'<div style="margin-top:7px;font-size:14px;line-height:1.65;color:#374151;">{_text(request.admin_note)}</div></div>'
        if request.admin_note
        else ""
    )
    content = f"""
      <div style="padding:18px;border-radius:12px;background:#f9fafb;border:1px solid #edf0f2;">
        <div style="font-size:12px;color:#6b7280;text-transform:uppercase;font-weight:800;">{_tr(company, 'Offre demandée', 'Requested plan')}</div>
        <div style="margin-top:6px;font-size:21px;color:#111827;font-weight:900;">{_text(getattr(plan, 'name', None), request.requested_plan_code)}</div>
        <div style="margin-top:6px;font-size:14px;color:#4b5563;">{_tr(company, 'Facturation', 'Billing')} {cycle} · {_money(request.quoted_amount, request.currency)}</div>
        <div style="margin-top:14px;font-size:14px;color:{accent};font-weight:900;">{_tr(company, 'Demande', 'Request')} {status}</div>
      </div>
      {response}
    """
    return _layout(
        user=company,
        preheader=_tr(company, f"Votre demande de mise à niveau a été {status}.", f"Your upgrade request was {status}."),
        eyebrow=_tr(company, "Abonnements Trade Care", "Trade Care subscriptions"),
        title=_tr(company, f"Votre demande a été {status}", f"Your request was {status}"),
        introduction=(
            _tr(company, "Votre nouvelle offre est désormais active pour votre entreprise.", "Your new plan is now active for your company.")
            if approved
            else _tr(company, "Le Super Admin a examiné votre demande de changement d’offre.", "The Super Admin reviewed your plan change request.")
        ),
        content=content,
        badge=_tr(company, "Mise à niveau", "Upgrade"),
        sender_name="Trade Care",
        contact_email=settings.MAIL_FROM,
        use_company_logo=False,
    )
