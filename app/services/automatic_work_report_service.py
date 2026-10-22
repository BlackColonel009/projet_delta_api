from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.model_commande import CommandeVente, LigneCommandeVente
from app.models.model_client import Client
from app.models.model_depot import Depot
from app.models.model_enterprise import Enterprise, EnterpriseGroup
from app.models.model_facture import Facture, TypeFacture
from app.models.model_intervention import Intervention
from app.models.model_notification import Notification
from app.models.model_paiement import Paiement
from app.models.model_produit import Produit
from app.models.model_stock_arrival import StockArrival, StockArrivalLine
from app.models.model_unite_produit import UniteProduit
from app.models.model_laundry import LaundryOrder, LaundryOrderEvent, LaundryPayment
from app.models.model_vehicle_rental import (
    VehicleReservation,
    VehicleRentalCharge,
    VehicleRentalEvent,
    VehicleRentalPayment,
)
from app.services.work_report_formatting import format_work_report
from app.models.model_property_rental import (
    PropertyInspection,
    PropertyMaintenance,
    PropertyOccupancy,
    PropertyPayment,
    PropertyPaymentDue,
)
from app.models.model_rapport import Rapport
from app.models.model_user import User


AUTOMATIC_SOURCE = "tradecare_daily"
EMPTY_MESSAGE = "Aucun rapport disponible signalé par Trade Care aujourd’hui."
_COMPLETED_INTERVENTION_STATUSES = {
    "termine", "terminé", "terminee", "terminée", "completed", "done",
    "cloture", "clôturé", "cloturee", "clôturée",
}
_CANCELLED_STATUSES = {
    "cancelled", "canceled", "annule", "annulé", "annulee", "annulée",
}
_MAX_NEXT_STEPS_PER_KIND = 10

DEFAULT_CONFIG = {
    "detail_level": "detailed",
    "list_style": "numbered",
    "include_amounts": True,
    "include_sales": True,
    "include_products": True,
    "include_product_units": True,
    "include_arrivals": True,
    "include_interventions": True,
    "include_consignments": True,
    "include_payments": True,
    "include_status_changes": True,
    "include_maintenance": True,
    "include_next_steps": True,
    "publish_when_empty": True,
}


def _timezone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Africa/Lome")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _utc_bounds(day: date, timezone_name: str | None) -> tuple[datetime, datetime]:
    zone = _timezone(timezone_name)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day, time.max, tzinfo=zone)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _money(value: float, currency: str) -> str:
    return f"{float(value or 0):,.0f} {currency}".replace(",", " ")


def _invoice_state(
    invoice: Facture | None,
    paid: float,
    *,
    include_amounts: bool = True,
) -> str:
    if invoice is None:
        return "facture non générée"
    total = float(invoice.total_ttc or 0)
    if total <= 0 or paid >= total - 0.01:
        return "soldée"
    if paid > 0:
        if include_amounts:
            return f"partiellement réglée (reste {_money(total - paid, invoice.devise or 'XOF')})"
        return "partiellement réglée"
    return "non soldée"


def _deposit_invoice_state(invoice) -> str:
    if invoice is None:
        return "non générée"
    status = (invoice.statut or "").lower()
    if invoice.date_paiement or status in {
        "paye", "payee", "payé", "payée", "solde", "soldée"
    }:
        return "soldée"
    return "non soldée"


def _intervention_next_step(intervention: Intervention) -> str:
    client_name = intervention.client.nom if intervention.client else "client non renseigné"
    subject = (
        intervention.description
        or intervention.produit_ex
        or f"intervention n°{intervention.id}"
    )
    status = intervention.statut or "non renseigné"
    return (
        f"Terminer l’intervention « {subject} » pour {client_name} "
        f"(statut actuel : {status})."
    )


def _invoice_next_step(
    invoice: Facture,
    paid: float,
    currency: str,
    *,
    include_amounts: bool,
) -> str:
    client_name = invoice.client.nom if invoice.client else "client non renseigné"
    total = float(invoice.total_ttc or 0)
    remaining = max(total - float(paid or 0), 0)
    reference = f"facture n°{invoice.id}"
    if not include_amounts:
        return f"Relancer {client_name} : la {reference} n’est pas encore soldée."
    if paid <= 0:
        return (
            f"Le client {client_name} nous doit toujours une somme de "
            f"{_money(remaining, currency)} sur la {reference}."
        )
    return (
        f"Le client {client_name} a déjà réglé {_money(paid, currency)} ; "
        f"il lui reste à payer {_money(remaining, currency)} sur la {reference}."
    )


def _commerce_next_steps(
    db: Session,
    enterprise: Enterprise,
    config: dict,
) -> list[str]:
    if not config["include_next_steps"]:
        return []
    steps: list[str] = []

    if config["include_interventions"]:
        terminal_statuses = tuple(
            _COMPLETED_INTERVENTION_STATUSES | _CANCELLED_STATUSES
        )
        open_interventions = (
            db.query(Intervention)
            .options(joinedload(Intervention.client))
            .filter(
                Intervention.enterprise_id == enterprise.id,
                or_(
                    Intervention.statut.is_(None),
                    func.lower(Intervention.statut).notin_(terminal_statuses),
                ),
            )
            .order_by(Intervention.date_intervention, Intervention.id)
            .limit(_MAX_NEXT_STEPS_PER_KIND + 1)
            .all()
        )
        for intervention in open_interventions[:_MAX_NEXT_STEPS_PER_KIND]:
            steps.append(_intervention_next_step(intervention))
        if len(open_interventions) > _MAX_NEXT_STEPS_PER_KIND:
            steps.append("D’autres interventions restent également à terminer.")

    if config["include_sales"]:
        payment_totals = (
            db.query(
                Paiement.facture_id.label("facture_id"),
                func.coalesce(func.sum(Paiement.montant), 0).label("paid"),
            )
            .group_by(Paiement.facture_id)
            .subquery()
        )
        paid_amount = func.coalesce(payment_totals.c.paid, 0)
        unpaid_rows = (
            db.query(Facture, paid_amount)
            .options(joinedload(Facture.client))
            .outerjoin(payment_totals, payment_totals.c.facture_id == Facture.id)
            .filter(
                Facture.enterprise_id == enterprise.id,
                Facture.type == TypeFacture.vente,
                or_(
                    Facture.statut.is_(None),
                    func.lower(Facture.statut).notin_(tuple(_CANCELLED_STATUSES)),
                ),
                func.coalesce(Facture.total_ttc, 0) > paid_amount,
            )
            .order_by(Facture.date_creation, Facture.id)
            .limit(_MAX_NEXT_STEPS_PER_KIND + 1)
            .all()
        )
        for invoice, paid in unpaid_rows[:_MAX_NEXT_STEPS_PER_KIND]:
            steps.append(
                _invoice_next_step(
                    invoice,
                    float(paid or 0),
                    enterprise.currency or invoice.devise or "XOF",
                    include_amounts=config["include_amounts"],
                )
            )
        if len(unpaid_rows) > _MAX_NEXT_STEPS_PER_KIND:
            steps.append("D’autres factures clients restent également à recouvrer.")

    return steps


def _append_next_steps(lines: list[str], steps: list[str]) -> None:
    if not steps:
        return
    lines.extend(["", "PROCHAINES ÉTAPES PROPOSÉES"])
    lines.extend(f"• {step}" for step in steps)


def _config(enterprise: Enterprise) -> dict:
    return {**DEFAULT_CONFIG, **(enterprise.automatic_work_report_config or {})}


def _finish(lines: list[str]) -> str:
    content = "\n".join(lines)
    if len(content) > 4950:
        content = content[:4850].rsplit("\n", 1)[0]
        content += "\n\n… Rapport abrégé par Trade Care en raison du volume d’activité."
    return content


def _header(enterprise: Enterprise, report_day: date, summary: list[str]) -> list[str]:
    return [
        f"RAPPORT JOURNALIER AUTOMATIQUE — {report_day.strftime('%d/%m/%Y')}",
        f"Entreprise : {enterprise.name}",
        "Généré automatiquement par Trade Care.",
        "",
        "SYNTHÈSE",
        *summary,
    ]


def _arrival_report_line(arrival: StockArrival) -> str:
    products = ", ".join(
        f"{line.product.nom if line.product else 'Produit'} ×{line.quantity}"
        for line in arrival.lines
    ) or "Aucun produit renseigné"
    reference = f" — Référence : {arrival.reference}" if arrival.reference else ""
    author = (
        f" — Enregistré par : {arrival.created_by_name}"
        if arrival.created_by_name
        else ""
    )
    return (
        f"• {arrival.created_at.strftime('%H:%M')} — {arrival.name}{reference} — "
        f"{products} — Statut : {arrival.status}{author}."
    )


def _build_commerce_report(
    db: Session,
    enterprise: Enterprise,
    report_day: date,
) -> str:
    start, end = _utc_bounds(report_day, enterprise.timezone)
    currency = enterprise.currency or "XOF"
    config = _config(enterprise)

    sales = [] if not config["include_sales"] else (
        db.query(CommandeVente)
        .options(
            joinedload(CommandeVente.client),
            selectinload(CommandeVente.lignes).joinedload(LigneCommandeVente.produit),
        )
        .filter(
            CommandeVente.enterprise_id == enterprise.id,
            CommandeVente.date_commande >= start,
            CommandeVente.date_commande <= end,
        )
        .order_by(CommandeVente.date_commande)
        .all()
    )
    sale_ids = [sale.id for sale in sales]
    invoices = {}
    paid_by_invoice = {}
    if sale_ids:
        invoice_rows = db.query(Facture).filter(
            Facture.enterprise_id == enterprise.id,
            Facture.commande_id.in_(sale_ids),
        ).all()
        invoices = {invoice.commande_id: invoice for invoice in invoice_rows}
        invoice_ids = [invoice.id for invoice in invoice_rows]
        if invoice_ids:
            paid_by_invoice = dict(
                db.query(Paiement.facture_id, func.coalesce(func.sum(Paiement.montant), 0))
                .filter(Paiement.facture_id.in_(invoice_ids))
                .group_by(Paiement.facture_id)
                .all()
            )

    products = [] if not config["include_products"] else (
        db.query(Produit)
        .options(joinedload(Produit.categorie))
        .filter(
            Produit.enterprise_id == enterprise.id,
            Produit.date_creation >= start,
            Produit.date_creation <= end,
            Produit.date_suppression.is_(None),
        )
        .order_by(Produit.date_creation)
        .all()
    )
    product_ids = {product.id for product in products}
    unit_rows = []
    if config["include_product_units"]:
        unit_rows = (
            db.query(
                UniteProduit.produit_id,
                func.count(UniteProduit.id),
                func.min(UniteProduit.date_creation),
            )
            .filter(
                UniteProduit.enterprise_id == enterprise.id,
                UniteProduit.date_creation >= start,
                UniteProduit.date_creation <= end,
                UniteProduit.produit_id.isnot(None),
            )
            .group_by(UniteProduit.produit_id)
            .all()
        )
    added_units = [row for row in unit_rows if row[0] not in product_ids]
    added_product_names = {}
    if added_units:
        added_product_names = dict(
            db.query(Produit.id, Produit.nom)
            .filter(Produit.id.in_([row[0] for row in added_units]))
            .all()
        )

    arrivals = [] if not config["include_arrivals"] else (
        db.query(StockArrival)
        .options(
            selectinload(StockArrival.lines).joinedload(StockArrivalLine.product),
        )
        .filter(
            StockArrival.enterprise_id == enterprise.id,
            StockArrival.created_at >= start,
            StockArrival.created_at <= end,
            StockArrival.status != "cancelled",
        )
        .order_by(StockArrival.created_at)
        .all()
    )

    interventions = [] if not config["include_interventions"] else (
        db.query(Intervention)
        .options(joinedload(Intervention.client), selectinload(Intervention.produits))
        .filter(
            Intervention.enterprise_id == enterprise.id,
            Intervention.date_intervention >= start,
            Intervention.date_intervention <= end,
        )
        .order_by(Intervention.date_intervention)
        .all()
    )
    deposits = [] if not config["include_consignments"] else (
        db.query(Depot)
        .options(
            joinedload(Depot.client),
            joinedload(Depot.service),
            joinedload(Depot.facture),
        )
        .filter(
            Depot.enterprise_id == enterprise.id,
            Depot.date_depot >= start,
            Depot.date_depot <= end,
        )
        .order_by(Depot.date_depot)
        .all()
    )
    next_steps = _commerce_next_steps(db, enterprise, config)

    if (
        not sales
        and not products
        and not added_units
        and not arrivals
        and not interventions
        and not deposits
        and not next_steps
    ):
        return EMPTY_MESSAGE

    lines = _header(enterprise, report_day, [
        f"• Ventes enregistrées : {len(sales)}",
        f"• Produits enregistrés : {len(products)}",
        f"• Ajouts d’unités au stock : {sum(int(row[1]) for row in added_units)}",
        f"• Nouveaux arrivages : {len(arrivals)}",
        f"• Interventions enregistrées : {len(interventions)}",
        f"• Consignes enregistrées : {len(deposits)}",
        f"• Actions de suivi proposées : {len(next_steps)}",
    ])

    if config["detail_level"] == "compact":
        _append_next_steps(lines, next_steps)
        return _finish(lines)

    if sales:
        lines.extend(["", "VENTES"])
        for sale in sales:
            invoice = invoices.get(sale.id)
            paid = float(paid_by_invoice.get(invoice.id, 0) if invoice else 0)
            sale_products = ", ".join(
                f"{line.produit.nom if line.produit else line.description or 'Produit'} ×{line.quantite}"
                for line in sale.lignes
            ) or "Produit non renseigné"
            lines.append(
                f"• {sale.date_commande.strftime('%H:%M')} — "
                f"{sale.client.nom if sale.client else 'Client non renseigné'} — "
                f"{sale_products}"
                f"{' — ' + _money(sale.total_ttc, currency) if config['include_amounts'] else ''} — "
                f"Facture {_invoice_state(invoice, paid, include_amounts=config['include_amounts'])}."
            )

    if products or added_units:
        lines.extend(["", "PRODUITS ENREGISTRÉS"])
        for product in products:
            amount = (
                f" — Prix de vente : {_money(product.prix_vente, currency)}"
                if config["include_amounts"] else ""
            )
            lines.append(
                f"• {product.date_creation.strftime('%H:%M')} — {product.nom} — "
                f"Catégorie : {product.categorie.nom if product.categorie else 'Non renseignée'} — "
                f"Quantité initiale : {product.quantite or 0}{amount}."
            )
        for product_id, quantity, created_at in added_units:
            lines.append(
                f"• {created_at.strftime('%H:%M')} — "
                f"{added_product_names.get(product_id, 'Produit')} — "
                f"{int(quantity)} nouvelle(s) unité(s) ajoutée(s)."
            )

    if arrivals:
        lines.extend(["", "NOUVEAUX ARRIVAGES"])
        lines.extend(_arrival_report_line(arrival) for arrival in arrivals)

    if interventions:
        lines.extend(["", "INTERVENTIONS"])
        for item in interventions:
            products = ", ".join(product.nom for product in item.produits)
            subject = item.description or item.produit_ex or "Intervention sans description"
            details = f" — Produits : {products}" if products else ""
            if item.commentaire_ex:
                details += f" — Observation : {item.commentaire_ex}"
            lines.append(
                f"• {item.date_intervention.strftime('%H:%M')} — "
                f"{item.client.nom if item.client else 'Client non renseigné'} — "
                f"{subject} — Statut : {item.statut}{details}."
            )

    if deposits:
        lines.extend(["", "CONSIGNES"])
        for item in deposits:
            invoice_state = _deposit_invoice_state(item.facture)
            lines.append(
                f"• {item.date_depot.strftime('%H:%M')} — "
                f"{item.client.nom if item.client else 'Client non renseigné'} — "
                f"{item.description_bien} ×{item.quantite} — "
                f"Service : {item.service.nom if item.service else 'Non renseigné'} — "
                f"Statut : {item.statut} — Facture {invoice_state}."
            )

    _append_next_steps(lines, next_steps)

    return _finish(lines)


def _build_laundry_report(db: Session, enterprise: Enterprise, report_day: date) -> str:
    start, end = _utc_bounds(report_day, enterprise.timezone)
    config = _config(enterprise)
    orders = (
        db.query(LaundryOrder)
        .options(joinedload(LaundryOrder.client), selectinload(LaundryOrder.items))
        .filter(
            LaundryOrder.enterprise_id == enterprise.id,
            LaundryOrder.received_at >= start,
            LaundryOrder.received_at <= end,
        ).order_by(LaundryOrder.received_at).all()
    )
    events = [] if not config["include_status_changes"] else (
        db.query(LaundryOrderEvent)
        .join(LaundryOrder, LaundryOrder.id == LaundryOrderEvent.order_id)
        .options(joinedload(LaundryOrderEvent.order))
        .filter(
            LaundryOrder.enterprise_id == enterprise.id,
            LaundryOrderEvent.created_at >= start,
            LaundryOrderEvent.created_at <= end,
        ).order_by(LaundryOrderEvent.created_at).all()
    )
    payments = [] if not config["include_payments"] else (
        db.query(LaundryPayment, LaundryOrder.order_number)
        .join(LaundryOrder, LaundryOrder.id == LaundryPayment.order_id)
        .filter(
            LaundryPayment.enterprise_id == enterprise.id,
            LaundryPayment.created_at >= start,
            LaundryPayment.created_at <= end,
        ).order_by(LaundryPayment.created_at).all()
    )
    if not orders and not events and not payments:
        return EMPTY_MESSAGE
    lines = _header(enterprise, report_day, [
        f"• Commandes reçues : {len(orders)}",
        f"• Changements de statut : {len(events)}",
        f"• Paiements enregistrés : {len(payments)}",
    ])
    if config["detail_level"] == "compact":
        return _finish(lines)
    if orders:
        lines.extend(["", "COMMANDES DE PRESSING"])
        for order in orders:
            items = ", ".join(f"{item.category} ×{item.quantity}" for item in order.items)
            amount = f" — {_money(order.total, enterprise.currency)}" if config["include_amounts"] else ""
            lines.append(
                f"• {order.received_at.strftime('%H:%M')} — {order.order_number} — "
                f"{order.client.nom if order.client else 'Client non renseigné'} — "
                f"{items or 'Articles non renseignés'} — Statut : {order.status}{amount}."
            )
    if events:
        lines.extend(["", "MOUVEMENTS"])
        for event in events:
            lines.append(
                f"• {event.created_at.strftime('%H:%M')} — {event.order.order_number} — "
                f"{event.from_status or 'début'} → {event.to_status} — Agent : {event.agent_name}."
            )
    if payments:
        lines.extend(["", "PAIEMENTS"])
        for payment, order_number in payments:
            amount = _money(payment.amount, enterprise.currency) if config["include_amounts"] else "Montant masqué"
            lines.append(
                f"• {payment.created_at.strftime('%H:%M')} — {order_number} — "
                f"{amount} — {payment.payment_method} — Agent : {payment.agent_name}."
            )
    return _finish(lines)


def _build_vehicle_report(db: Session, enterprise: Enterprise, report_day: date) -> str:
    start, end = _utc_bounds(report_day, enterprise.timezone)
    config = _config(enterprise)
    reservations = (
        db.query(VehicleReservation)
        .options(joinedload(VehicleReservation.client), joinedload(VehicleReservation.vehicle))
        .filter(
            VehicleReservation.enterprise_id == enterprise.id,
            VehicleReservation.created_at >= start,
            VehicleReservation.created_at <= end,
        ).order_by(VehicleReservation.created_at).all()
    )
    events = [] if not config["include_status_changes"] else (
        db.query(VehicleRentalEvent)
        .join(VehicleReservation, VehicleReservation.id == VehicleRentalEvent.reservation_id)
        .options(joinedload(VehicleRentalEvent.reservation).joinedload(VehicleReservation.vehicle))
        .filter(
            VehicleReservation.enterprise_id == enterprise.id,
            VehicleRentalEvent.created_at >= start,
            VehicleRentalEvent.created_at <= end,
        ).order_by(VehicleRentalEvent.created_at).all()
    )
    payments = [] if not config["include_payments"] else (
        db.query(VehicleRentalPayment, VehicleReservation.reservation_number)
        .join(VehicleReservation, VehicleReservation.id == VehicleRentalPayment.reservation_id)
        .filter(
            VehicleRentalPayment.enterprise_id == enterprise.id,
            VehicleRentalPayment.created_at >= start,
            VehicleRentalPayment.created_at <= end,
        ).order_by(VehicleRentalPayment.created_at).all()
    )
    charges = (
        db.query(VehicleRentalCharge, VehicleReservation.reservation_number)
        .join(VehicleReservation, VehicleReservation.id == VehicleRentalCharge.reservation_id)
        .filter(
            VehicleRentalCharge.enterprise_id == enterprise.id,
            VehicleRentalCharge.created_at >= start,
            VehicleRentalCharge.created_at <= end,
        ).order_by(VehicleRentalCharge.created_at).all()
    )
    if not reservations and not events and not payments and not charges:
        return EMPTY_MESSAGE
    lines = _header(enterprise, report_day, [
        f"• Réservations créées : {len(reservations)}",
        f"• Mouvements de véhicules : {len(events)}",
        f"• Paiements enregistrés : {len(payments)}",
        f"• Frais et pénalités : {len(charges)}",
    ])
    if config["detail_level"] == "compact":
        return _finish(lines)
    if reservations:
        lines.extend(["", "RÉSERVATIONS ET LOCATIONS"])
        for item in reservations:
            amount = f" — {_money(item.estimated_total, enterprise.currency)}" if config["include_amounts"] else ""
            lines.append(
                f"• {item.created_at.strftime('%H:%M')} — {item.reservation_number} — "
                f"{item.client.nom if item.client else 'Client non renseigné'} — "
                f"{item.vehicle.name if item.vehicle else 'Véhicule non renseigné'} — "
                f"Statut : {item.status}{amount}."
            )
    if events:
        lines.extend(["", "MOUVEMENTS"])
        for event in events:
            vehicle = event.reservation.vehicle
            lines.append(
                f"• {event.created_at.strftime('%H:%M')} — "
                f"{vehicle.name if vehicle else event.reservation.reservation_number} — "
                f"{event.from_status or 'début'} → {event.to_status}."
            )
    if payments or charges:
        lines.extend(["", "PAIEMENTS ET FRAIS"])
        for payment, number in payments:
            amount = _money(payment.amount, enterprise.currency) if config["include_amounts"] else "Montant masqué"
            lines.append(f"• {payment.created_at.strftime('%H:%M')} — {number} — {payment.kind} : {amount} ({payment.payment_method}).")
        for charge, number in charges:
            amount = _money(charge.amount, enterprise.currency) if config["include_amounts"] else "Montant masqué"
            lines.append(f"• {charge.created_at.strftime('%H:%M')} — {number} — {charge.label} : {amount}.")
    return _finish(lines)


def _build_property_report(db: Session, enterprise: Enterprise, report_day: date) -> str:
    start, end = _utc_bounds(report_day, enterprise.timezone)
    config = _config(enterprise)
    occupancies = (
        db.query(PropertyOccupancy)
        .options(joinedload(PropertyOccupancy.client), joinedload(PropertyOccupancy.unit))
        .filter(
            PropertyOccupancy.enterprise_id == enterprise.id,
            PropertyOccupancy.created_at >= start,
            PropertyOccupancy.created_at <= end,
        ).order_by(PropertyOccupancy.created_at).all()
    )
    dues = (
        db.query(PropertyPaymentDue)
        .options(joinedload(PropertyPaymentDue.occupancy))
        .filter(
            PropertyPaymentDue.enterprise_id == enterprise.id,
            PropertyPaymentDue.due_date >= start,
            PropertyPaymentDue.due_date <= end,
        ).order_by(PropertyPaymentDue.due_date).all()
    )
    payments = [] if not config["include_payments"] else (
        db.query(PropertyPayment, PropertyOccupancy.contract_number)
        .join(PropertyOccupancy, PropertyOccupancy.id == PropertyPayment.occupancy_id)
        .filter(
            PropertyPayment.enterprise_id == enterprise.id,
            PropertyPayment.created_at >= start,
            PropertyPayment.created_at <= end,
        ).order_by(PropertyPayment.created_at).all()
    )
    maintenance = [] if not config["include_maintenance"] else (
        db.query(PropertyMaintenance)
        .filter(
            PropertyMaintenance.enterprise_id == enterprise.id,
            PropertyMaintenance.created_at >= start,
            PropertyMaintenance.created_at <= end,
        ).order_by(PropertyMaintenance.created_at).all()
    )
    inspections = [] if not config["include_maintenance"] else (
        db.query(PropertyInspection, PropertyOccupancy.contract_number)
        .join(PropertyOccupancy, PropertyOccupancy.id == PropertyInspection.occupancy_id)
        .filter(
            PropertyInspection.enterprise_id == enterprise.id,
            PropertyInspection.created_at >= start,
            PropertyInspection.created_at <= end,
        ).order_by(PropertyInspection.created_at).all()
    )
    if not occupancies and not dues and not payments and not maintenance and not inspections:
        return EMPTY_MESSAGE
    lines = _header(enterprise, report_day, [
        f"• Contrats créés : {len(occupancies)}",
        f"• Échéances du jour : {len(dues)}",
        f"• Paiements enregistrés : {len(payments)}",
        f"• Maintenances et états des lieux : {len(maintenance) + len(inspections)}",
    ])
    if config["detail_level"] == "compact":
        return _finish(lines)
    if occupancies:
        lines.extend(["", "CONTRATS ET OCCUPATIONS"])
        for item in occupancies:
            amount = f" — {_money(item.total_amount, enterprise.currency)}" if config["include_amounts"] else ""
            lines.append(
                f"• {item.created_at.strftime('%H:%M')} — {item.contract_number} — "
                f"{item.client.nom if item.client else 'Client non renseigné'} — "
                f"{item.unit.name if item.unit else 'Bien non renseigné'} — Statut : {item.status}{amount}."
            )
    if dues or payments:
        lines.extend(["", "LOYERS ET PAIEMENTS"])
        for due in dues:
            amount = _money(due.amount, enterprise.currency) if config["include_amounts"] else "Montant masqué"
            lines.append(f"• Échéance {due.occupancy.contract_number} — {amount} — Statut : {due.status}.")
        for payment, number in payments:
            amount = _money(payment.amount, enterprise.currency) if config["include_amounts"] else "Montant masqué"
            lines.append(f"• {payment.created_at.strftime('%H:%M')} — {number} — {payment.kind} : {amount} ({payment.payment_method}).")
    if maintenance or inspections:
        lines.extend(["", "MAINTENANCE ET ÉTATS DES LIEUX"])
        for item in maintenance:
            lines.append(f"• {item.created_at.strftime('%H:%M')} — {item.title} — Priorité : {item.priority} — Statut : {item.status}.")
        for inspection, number in inspections:
            lines.append(f"• {inspection.created_at.strftime('%H:%M')} — {number} — État des lieux : {inspection.inspection_type} — Agent : {inspection.agent_name}.")
    return _finish(lines)


def build_daily_work_report(db: Session, enterprise: Enterprise, report_day: date) -> str:
    builders = {
        "laundry": _build_laundry_report,
        "vehicle_rental": _build_vehicle_report,
        "property_rental": _build_property_report,
    }
    return builders.get(enterprise.business_type, _build_commerce_report)(
        db, enterprise, report_day
    )


def generate_daily_work_report(
    db: Session,
    enterprise: Enterprise,
    report_day: date,
    *,
    refresh_existing: bool = False,
) -> Rapport | None:
    existing = db.query(Rapport).filter(
        Rapport.enterprise_id == enterprise.id,
        Rapport.source == AUTOMATIC_SOURCE,
        Rapport.source_date == report_day,
    ).first()
    raw_content = build_daily_work_report(db, enterprise, report_day)
    config = _config(enterprise)
    if raw_content == EMPTY_MESSAGE and not config["publish_when_empty"]:
        return existing
    content = format_work_report(raw_content, config.get("list_style"))
    if existing:
        if refresh_existing:
            existing.contenu = content
            existing.date_modification = datetime.utcnow()
            db.commit()
            db.refresh(existing)
        return existing

    group = db.query(EnterpriseGroup).filter(EnterpriseGroup.id == enterprise.group_id).first()
    report = Rapport(
        contenu=content,
        date_rapport=report_day,
        user_id=group.owner_user_id if group else None,
        enterprise_id=enterprise.id,
        source=AUTOMATIC_SOURCE,
        source_date=report_day,
    )
    db.add(report)
    if group:
        db.add(
            Notification(
                titre="Nouveau rapport de travail",
                message=(
                    f"Trade Care a généré le rapport journalier automatique "
                    f"de {enterprise.name}."
                ),
                parent_user_id=group.owner_user_id,
                enterprise_id=enterprise.id,
                is_read=False,
            )
        )
    try:
        db.commit()
        db.refresh(report)
        return report
    except IntegrityError:
        db.rollback()
        return db.query(Rapport).filter(
            Rapport.enterprise_id == enterprise.id,
            Rapport.source == AUTOMATIC_SOURCE,
            Rapport.source_date == report_day,
        ).one()


def dispatch_scheduled_daily_reports(db: Session, now_utc: datetime | None = None) -> int:
    """Generate one isolated report per enabled enterprise at its configured time."""
    now_utc = now_utc or datetime.now(timezone.utc)
    enterprises = db.query(Enterprise).filter(
        Enterprise.status == "active",
        Enterprise.automatic_work_report_enabled.is_(True),
    ).all()
    generated = 0
    for enterprise in enterprises:
        group = db.query(EnterpriseGroup).filter(
            EnterpriseGroup.id == enterprise.group_id
        ).first()
        owner = db.query(User).filter(
            User.id == group.owner_user_id if group else -1
        ).first()
        if owner is None:
            continue
        local_now = now_utc.astimezone(_timezone(enterprise.timezone))
        hour = (
            owner.daily_report_reminder_hour
            if enterprise.automatic_work_report_inherit_time
            else enterprise.automatic_work_report_hour
        )
        minute = (
            owner.daily_report_reminder_minute
            if enterprise.automatic_work_report_inherit_time
            else enterprise.automatic_work_report_minute
        )
        scheduled_minutes = int(hour or 0) * 60 + int(minute or 0)
        if local_now.hour * 60 + local_now.minute < scheduled_minutes:
            continue
        exists = db.query(Rapport.id).filter(
            Rapport.enterprise_id == enterprise.id,
            Rapport.source == AUTOMATIC_SOURCE,
            Rapport.source_date == local_now.date(),
        ).first()
        if exists:
            continue
        report = generate_daily_work_report(db, enterprise, local_now.date())
        if report is not None:
            generated += 1
    return generated
