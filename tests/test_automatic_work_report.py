import unittest
from datetime import date, datetime
from types import SimpleNamespace

from app.services.automatic_work_report_service import (
    DEFAULT_CONFIG,
    EMPTY_MESSAGE,
    _config,
    _arrival_report_line,
    _commerce_next_steps,
    _deposit_invoice_state,
    _intervention_next_step,
    _invoice_next_step,
    _invoice_state,
    _format_automatic_report,
    _summary,
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

    def test_open_intervention_generates_a_clear_next_step(self):
        intervention = SimpleNamespace(
            id=8,
            client=SimpleNamespace(nom="Entreprise Kossi"),
            description="Réparer le climatiseur",
            produit_ex=None,
            statut="en cours",
        )
        result = _intervention_next_step(intervention)
        self.assertIn("Terminer l’intervention", result)
        self.assertIn("Réparer le climatiseur", result)
        self.assertIn("Entreprise Kossi", result)

    def test_unpaid_invoice_next_step_distinguishes_unpaid_and_partial(self):
        invoice = SimpleNamespace(
            id=15,
            client=SimpleNamespace(nom="Client Delta"),
            total_ttc=100_000,
        )
        unpaid = _invoice_next_step(
            invoice, 0, "XOF", include_amounts=True
        )
        partial = _invoice_next_step(
            invoice, 40_000, "XOF", include_amounts=True
        )
        self.assertIn("nous doit toujours", unpaid)
        self.assertIn("100 000 XOF", unpaid)
        self.assertIn("reste à payer 60 000 XOF", partial)

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
        self.assertTrue(config["include_arrivals"])
        self.assertTrue(config["include_next_steps"])

    def test_arrival_line_lists_products_quantities_and_author(self):
        arrival = SimpleNamespace(
            created_at=datetime(2026, 10, 22, 14, 35),
            name="Livraison octobre",
            reference="ARR-1022",
            status="validated",
            created_by_name="Afi",
            lines=[
                SimpleNamespace(
                    product=SimpleNamespace(nom="Téléviseur"),
                    quantity=4,
                ),
                SimpleNamespace(
                    product=SimpleNamespace(nom="Ventilateur"),
                    quantity=2,
                ),
            ],
        )

        result = _arrival_report_line(arrival)

        self.assertIn("Livraison octobre", result)
        self.assertIn("Téléviseur ×4", result)
        self.assertIn("Ventilateur ×2", result)
        self.assertIn("Afi", result)

    def test_disabled_next_steps_do_not_query_or_generate_any_suggestion(self):
        self.assertEqual(
            _commerce_next_steps(
                None,
                SimpleNamespace(),
                {"include_next_steps": False},
            ),
            [],
        )

    def test_main_user_and_admin_can_manage_automatic_report(self):
        self.assertTrue(_can_manage_automatic_report(SimpleNamespace(is_main_user=True)))
        self.assertTrue(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="admin")
        ))
        self.assertTrue(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, role="Directeur")
        ))
        self.assertTrue(_can_manage_automatic_report(
            SimpleNamespace(is_main_user=False, is_superuser=True, role="")
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

    def test_automatic_report_style_is_applied_and_restarts_per_section(self):
        content = "SYNTHÈSE\n• Deux ventes\n• Un paiement\n\nVENTES\n• Vente A\n• Vente B"
        self.assertEqual(
            _format_automatic_report(content, "numbered"),
            "SYNTHÈSE\n1 - Deux ventes\n2 - Un paiement\n\nVENTES\n1 - Vente A\n2 - Vente B",
        )

    def test_automatic_summary_omits_disabled_sections(self):
        config = {"include_sales": False, "include_products": True}
        self.assertEqual(
            _summary(
                config,
                [
                    ("include_sales", "Ventes : 0"),
                    ("include_products", "Produits : 2"),
                    (None, "Activité principale : 1"),
                ],
            ),
            ["• Produits : 2", "• Activité principale : 1"],
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
