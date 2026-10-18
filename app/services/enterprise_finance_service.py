from calendar import month_abbr
from datetime import datetime

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.model_depense import Depense
from app.models.model_enterprise import Enterprise
from app.models.model_facture import Facture, TypeFacture
from app.models.model_facture_depot import FactureDepot
from app.models.model_laundry import LaundryOrder, LaundryPayment
from app.models.model_paiement import Paiement
from app.models.model_property_rental import (
    PropertyMaintenance,
    PropertyPayment,
    PropertyPaymentDue,
)
from app.models.model_vehicle_rental import (
    VehicleRentalPayment,
    VehicleReservation,
)


_CANCELLED = ("cancelled", "annule", "annulee", "annulé", "annulée")


def _sum(query) -> float:
    return float(query.scalar() or 0)


def _year_filter(column, year: int):
    return extract("year", column) == year


def _monthly(db: Session, column, amount, filters, year: int) -> list[float]:
    rows = (
        db.query(extract("month", column), func.coalesce(func.sum(amount), 0))
        .filter(*filters, _year_filter(column, year))
        .group_by(extract("month", column))
        .all()
    )
    values = [0.0] * 12
    for month, total in rows:
        if month:
            values[int(month) - 1] = float(total or 0)
    return values


def enterprise_finance_summary(
    db: Session,
    enterprise: Enterprise,
    year: int | None = None,
) -> dict:
    """Return one comparable financial view without mixing business ledgers.

    Deposits are deliberately kept outside revenue and net operating cash flow.
    """
    year = year or datetime.utcnow().year
    enterprise_id = enterprise.id
    business_type = enterprise.business_type or "commerce"
    generic_expenses = _sum(
        db.query(func.sum(Depense.montant)).filter(
            Depense.enterprise_id == enterprise_id,
            _year_filter(Depense.date_depense, year),
        )
    )
    expense_monthly = _monthly(
        db,
        Depense.date_depense,
        Depense.montant,
        [Depense.enterprise_id == enterprise_id],
        year,
    )
    deposits_held = 0.0
    overdue_count = 0
    operational_expenses = generic_expenses

    if business_type == "laundry":
        active = [
            LaundryOrder.enterprise_id == enterprise_id,
            func.lower(LaundryOrder.status).notin_(_CANCELLED),
        ]
        invoiced = _sum(
            db.query(func.sum(LaundryOrder.total)).filter(
                *active, _year_filter(LaundryOrder.received_at, year)
            )
        )
        collected = _sum(
            db.query(func.sum(LaundryPayment.amount)).filter(
                LaundryPayment.enterprise_id == enterprise_id,
                _year_filter(LaundryPayment.created_at, year),
            )
        )
        receivables = _sum(
            db.query(func.sum(LaundryOrder.total - LaundryOrder.paid_amount)).filter(
                *active, LaundryOrder.total > LaundryOrder.paid_amount
            )
        )
        invoiced_monthly = _monthly(
            db, LaundryOrder.received_at, LaundryOrder.total, active, year
        )
        collected_monthly = _monthly(
            db,
            LaundryPayment.created_at,
            LaundryPayment.amount,
            [LaundryPayment.enterprise_id == enterprise_id],
            year,
        )
    elif business_type == "vehicle_rental":
        active = [
            VehicleReservation.enterprise_id == enterprise_id,
            func.lower(VehicleReservation.status).notin_(_CANCELLED),
        ]
        invoiced = _sum(
            db.query(func.sum(VehicleReservation.estimated_total)).filter(
                *active, _year_filter(VehicleReservation.created_at, year)
            )
        )
        collected = _sum(
            db.query(func.sum(VehicleRentalPayment.amount)).filter(
                VehicleRentalPayment.enterprise_id == enterprise_id,
                VehicleRentalPayment.kind == "rental",
                _year_filter(VehicleRentalPayment.created_at, year),
            )
        )
        receivables = _sum(
            db.query(
                func.sum(
                    VehicleReservation.estimated_total
                    - VehicleReservation.paid_amount
                )
            ).filter(
                *active,
                VehicleReservation.estimated_total > VehicleReservation.paid_amount,
            )
        )
        deposits_paid = _sum(
            db.query(func.sum(VehicleRentalPayment.amount)).filter(
                VehicleRentalPayment.enterprise_id == enterprise_id,
                VehicleRentalPayment.kind == "deposit",
            )
        )
        deposits_refunded = _sum(
            db.query(func.sum(VehicleRentalPayment.amount)).filter(
                VehicleRentalPayment.enterprise_id == enterprise_id,
                VehicleRentalPayment.kind == "deposit_refund",
            )
        )
        deposits_held = max(0.0, deposits_paid - deposits_refunded)
        invoiced_monthly = _monthly(
            db,
            VehicleReservation.created_at,
            VehicleReservation.estimated_total,
            active,
            year,
        )
        collected_monthly = _monthly(
            db,
            VehicleRentalPayment.created_at,
            VehicleRentalPayment.amount,
            [
                VehicleRentalPayment.enterprise_id == enterprise_id,
                VehicleRentalPayment.kind == "rental",
            ],
            year,
        )
    elif business_type == "property_rental":
        invoiced = _sum(
            db.query(func.sum(PropertyPaymentDue.amount)).filter(
                PropertyPaymentDue.enterprise_id == enterprise_id,
                _year_filter(PropertyPaymentDue.due_date, year),
            )
        )
        collected = _sum(
            db.query(func.sum(PropertyPayment.amount)).filter(
                PropertyPayment.enterprise_id == enterprise_id,
                PropertyPayment.kind == "rent",
                _year_filter(PropertyPayment.created_at, year),
            )
        )
        receivables = _sum(
            db.query(
                func.sum(PropertyPaymentDue.amount - PropertyPaymentDue.paid_amount)
            ).filter(
                PropertyPaymentDue.enterprise_id == enterprise_id,
                PropertyPaymentDue.amount > PropertyPaymentDue.paid_amount,
            )
        )
        overdue_count = int(
            db.query(func.count(PropertyPaymentDue.id)).filter(
                PropertyPaymentDue.enterprise_id == enterprise_id,
                PropertyPaymentDue.due_date < datetime.utcnow(),
                PropertyPaymentDue.amount > PropertyPaymentDue.paid_amount,
            ).scalar()
            or 0
        )
        deposits_paid = _sum(
            db.query(func.sum(PropertyPayment.amount)).filter(
                PropertyPayment.enterprise_id == enterprise_id,
                PropertyPayment.kind == "deposit",
            )
        )
        deposits_refunded = _sum(
            db.query(func.sum(PropertyPayment.amount)).filter(
                PropertyPayment.enterprise_id == enterprise_id,
                PropertyPayment.kind == "deposit_refund",
            )
        )
        deposits_held = max(0.0, deposits_paid - deposits_refunded)
        maintenance = _sum(
            db.query(func.sum(PropertyMaintenance.actual_cost)).filter(
                PropertyMaintenance.enterprise_id == enterprise_id,
                _year_filter(PropertyMaintenance.created_at, year),
            )
        )
        operational_expenses += maintenance
        maintenance_monthly = _monthly(
            db,
            PropertyMaintenance.created_at,
            PropertyMaintenance.actual_cost,
            [PropertyMaintenance.enterprise_id == enterprise_id],
            year,
        )
        expense_monthly = [
            expense_monthly[index] + maintenance_monthly[index]
            for index in range(12)
        ]
        invoiced_monthly = _monthly(
            db,
            PropertyPaymentDue.due_date,
            PropertyPaymentDue.amount,
            [PropertyPaymentDue.enterprise_id == enterprise_id],
            year,
        )
        collected_monthly = _monthly(
            db,
            PropertyPayment.created_at,
            PropertyPayment.amount,
            [
                PropertyPayment.enterprise_id == enterprise_id,
                PropertyPayment.kind == "rent",
            ],
            year,
        )
    elif business_type == "legacy_consignment":
        active = [
            FactureDepot.enterprise_id == enterprise_id,
            func.lower(FactureDepot.statut).notin_(_CANCELLED),
        ]
        paid = [
            FactureDepot.enterprise_id == enterprise_id,
            func.lower(FactureDepot.statut).in_(
                ("paye", "payee", "payé", "payée", "solde", "soldée")
            ),
        ]
        invoiced = _sum(
            db.query(func.sum(FactureDepot.montant_ttc)).filter(
                *active, _year_filter(FactureDepot.date_facture, year)
            )
        )
        collected = _sum(
            db.query(func.sum(FactureDepot.montant_ttc)).filter(
                *paid, _year_filter(FactureDepot.date_paiement, year)
            )
        )
        total_invoiced = _sum(
            db.query(func.sum(FactureDepot.montant_ttc)).filter(*active)
        )
        total_collected = _sum(
            db.query(func.sum(FactureDepot.montant_ttc)).filter(*paid)
        )
        receivables = max(0.0, total_invoiced - total_collected)
        invoiced_monthly = _monthly(
            db, FactureDepot.date_facture, FactureDepot.montant_ttc, active, year
        )
        collected_monthly = _monthly(
            db,
            FactureDepot.date_paiement,
            FactureDepot.montant_ttc,
            paid,
            year,
        )
    else:
        sales = [
            Facture.enterprise_id == enterprise_id,
            Facture.type == TypeFacture.vente,
            func.lower(Facture.statut).notin_(_CANCELLED),
        ]
        invoiced = _sum(
            db.query(func.sum(Facture.total_ttc)).filter(
                *sales, _year_filter(Facture.date_creation, year)
            )
        )
        collected = _sum(
            db.query(func.sum(Paiement.montant))
            .join(Facture, Facture.id == Paiement.facture_id)
            .filter(
                Facture.enterprise_id == enterprise_id,
                Facture.type == TypeFacture.vente,
                _year_filter(Paiement.date_paiement, year),
            )
        )
        total_sales = _sum(db.query(func.sum(Facture.total_ttc)).filter(*sales))
        total_paid = _sum(
            db.query(func.sum(Paiement.montant))
            .join(Facture, Facture.id == Paiement.facture_id)
            .filter(
                Facture.enterprise_id == enterprise_id,
                Facture.type == TypeFacture.vente,
            )
        )
        receivables = max(0.0, total_sales - total_paid)
        invoiced_monthly = _monthly(
            db, Facture.date_creation, Facture.total_ttc, sales, year
        )
        collected_monthly = _monthly(
            db,
            Paiement.date_paiement,
            Paiement.montant,
            [
                Paiement.enterprise_id == enterprise_id,
                Paiement.facture_id.in_(
                    db.query(Facture.id).filter(Facture.type == TypeFacture.vente)
                ),
            ],
            year,
        )

    monthly = [
        {
            "month": index + 1,
            "label": month_abbr[index + 1],
            "invoiced": invoiced_monthly[index],
            "collected": collected_monthly[index],
            "expenses": expense_monthly[index],
        }
        for index in range(12)
    ]
    return {
        "enterprise_id": enterprise.id,
        "enterprise_name": enterprise.name,
        "business_type": business_type,
        "currency": enterprise.currency or "XOF",
        "year": year,
        "invoiced_revenue": invoiced,
        "collected_revenue": collected,
        "expenses": operational_expenses,
        "receivables": receivables,
        "net_cash_flow": collected - operational_expenses,
        "deposits_held": deposits_held,
        "overdue_count": overdue_count,
        "monthly": monthly,
    }
