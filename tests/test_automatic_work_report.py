import unittest
from datetime import date
from types import SimpleNamespace

from app.services.automatic_work_report_service import (
    DEFAULT_CONFIG,
    EMPTY_MESSAGE,
    _config,
    _deposit_invoice_state,
    _invoice_state,
    _utc_bounds,
)
from app.routes.rapport import _can_manage_automatic_report


class AutomaticWorkReportTests(unittest.TestCase):
    def test_empty_message_identifies_trade_care(self):
        self.assertIn("Trade Care", EMPTY_MESSAGE)

    def test_invoice_payment_states(self):
        invoice = SimpleNamespace(total_ttc=10_000, devise="XOF")
        self.assertEqual(_invoice_state(invoice, 0), "non soldée")
        self.assertIn("partiellement", _invoice_state(invoice, 4_000))
        self.assertEqual(_invoice_state(invoice, 10_000), "soldée")

    def test_consignment_invoice_state(self):
        paid = SimpleNamespace(statut="payée", date_paiement=None)
        pending = SimpleNamespace(statut="en_attente", date_paiement=None)
        self.assertEqual(_deposit_invoice_state(paid), "soldée")
        self.assertEqual(_deposit_invoice_state(pending), "non soldée")

    def test_lome_day_is_converted_to_utc_bounds(self):
        start, end = _utc_bounds(date(2026, 10, 18), "Africa/Lome")
        self.assertEqual(start.date(), date(2026, 10, 18))
        self.assertEqual(end.date(), date(2026, 10, 18))

    def test_report_config_keeps_defaults_and_overrides_selected_options(self):
        enterprise = SimpleNamespace(
            automatic_work_report_config={
                "detail_level": "compact",
                "include_amounts": False,
            }
        )
        config = _config(enterprise)
        self.assertEqual(config["detail_level"], "compact")
        self.assertFalse(config["include_amounts"])
        self.assertEqual(config["include_products"], DEFAULT_CONFIG["include_products"])
        self.assertTrue(config["include_product_units"])

    def test_main_user_and_admin_can_manage_automatic_report(self):
        self.assertTrue(_can_manage_automatic_report(SimpleNamespace(is_main_user=True)))
        self.assertTrue(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="admin")
        ))
        self.assertFalse(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="caissier")
        ))


if __name__ == "__main__":
    unittest.main()
