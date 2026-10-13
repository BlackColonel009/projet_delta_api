import unittest

from app.models.model_commande import LigneCommandeVente
from app.models.model_facture import LigneFacture
from app.routes.dashboard_financier import calculate_financial_results
from app.services.bilan_annuel_service import calcul_benefices


class FinancialConsistencyTests(unittest.TestCase):
    def test_profit_and_cash_flow_are_distinct(self):
        result = calculate_financial_results(
            invoiced_ht=1_000_000,
            cost_of_goods=600_000,
            expenses=100_000,
            collected=750_000,
            supplier_outflows=300_000,
        )

        self.assertEqual(result["gross_profit"], 400_000)
        self.assertEqual(result["net_profit"], 300_000)
        self.assertEqual(result["net_cash_flow"], 350_000)

    def test_annual_report_uses_cost_of_goods_not_all_purchases(self):
        gross, net = calcul_benefices(1_000_000, 600_000, {"total": 100_000})

        self.assertEqual(gross, 400_000)
        self.assertEqual(net, 300_000)

    def test_sale_and_invoice_lines_store_historical_cost(self):
        self.assertIn("cout_achat_unitaire", LigneCommandeVente.__table__.columns)
        self.assertIn("cout_achat_unitaire", LigneFacture.__table__.columns)


if __name__ == "__main__":
    unittest.main()
