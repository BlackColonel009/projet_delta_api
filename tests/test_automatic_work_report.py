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
from app.services.work_report_formatting import format_work_report


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
        self.assertTrue(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="Directeur")
        ))
        self.assertFalse(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="caissier")
        ))

    def test_report_lines_are_numbered_without_duplicate_prefixes(self):
        content = "Objet du rapport\n\nTravail effectué\nProduit vendu\n- Consigne enregistrée\n3) Paiement reçu"
        self.assertEqual(
            format_work_report(content, "numbered"),
            "Objet du rapport\n\nTravail effectué\n1 - Produit vendu\n2 - Consigne enregistrée\n3 - Paiement reçu",
        )

    def test_report_list_style_can_be_changed(self):
        self.assertEqual(
            format_work_report(
                "Objet\n\nRésultats obtenus\nProduit vendu\nPaiement reçu",
                "bullet",
            ),
            "Objet\n\nRésultats obtenus\n• Produit vendu\n• Paiement reçu",
        )

    def test_free_form_report_is_not_numbered(self):
        self.assertEqual(
            format_work_report("Rapport libre\nDeuxième ligne", "numbered"),
            "Rapport libre\nDeuxième ligne",
        )

    def test_structured_report_preserves_subject_and_restarts_each_section(self):
        content = """📌 Rapport boutique

Travail effectué
Produit vendu
Stock vérifié

Résultats obtenus
Facture soldée

Difficultés rencontrées
Aucune

Prochaines étapes
Contacter le client"""

        self.assertEqual(
            format_work_report(content, "numbered"),
            """📌 Rapport boutique

Travail effectué
1 - Produit vendu
2 - Stock vérifié

Résultats obtenus
1 - Facture soldée

Difficultés rencontrées
1 - Aucune

Prochaines étapes
1 - Contacter le client""",
        )


if __name__ == "__main__":
    unittest.main()
