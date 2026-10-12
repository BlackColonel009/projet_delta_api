from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.routes.export_financier import _build_stock_report, export_etat_stock


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def join(self, *args):
        return self

    def all(self):
        return self.rows


class _FakeDb:
    def __init__(self, results):
        self.results = iter(results)

    def query(self, *args):
        return _FakeQuery(next(self.results))


class StockExportTest(unittest.TestCase):
    def test_stock_report_handles_very_long_product_content(self):
        """Une cellule ne doit jamais devenir plus haute qu'une page ReportLab."""
        rows = [
            {
                "id": 82,
                "name": "Produit professionnel avec une désignation très longue " * 8,
                "characteristics": "Caractéristique technique détaillée " * 250,
                "traceability": [
                    f"TRACABILITE-TRES-LONGUE-{index:04d}-ABCDEFGHIJKLMN"
                    for index in range(240)
                ],
                "initial": 240,
                "available": 218,
                "price": 125000,
            }
        ]
        output = BytesIO()

        _build_stock_report(output, "FCFA", rows)

        pdf = output.getvalue()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertGreater(len(pdf), 5_000)

    def test_stock_report_accepts_empty_rows_and_missing_price(self):
        output = BytesIO()
        _build_stock_report(
            output,
            "FCFA",
            [
                {
                    "id": 1,
                    "name": "Produit sans prix",
                    "characteristics": None,
                    "traceability": [],
                    "initial": 0,
                    "available": 0,
                    "price": None,
                }
            ],
        )

        self.assertTrue(output.getvalue().startswith(b"%PDF"))

    def test_stock_endpoint_uses_declared_stock_when_product_has_no_units(self):
        products = [
            SimpleNamespace(
                id=10,
                nom="Produit classique",
                caracteristiques=None,
                quantite=17,
                prix_vente=2500,
            ),
            SimpleNamespace(
                id=11,
                nom="Produit tracé",
                caracteristiques="Série A",
                quantite=99,
                prix_vente=5000,
            ),
        ]
        units = [
            (11, "QR-001", "Disponible"),
            (11, "QR-002", "vendu"),
        ]
        current_user = SimpleNamespace(
            id=7,
            is_main_user=True,
            parent_user_id=None,
            parent_user=None,
            devise="FCFA",
        )

        with patch(
            "app.routes.export_financier._build_stock_report"
        ) as build_report:
            export_etat_stock(
                db=_FakeDb([products, units]),
                current_user=current_user,
            )

        rows = build_report.call_args.args[2]
        self.assertEqual(rows[0]["initial"], 17)
        self.assertEqual(rows[0]["available"], 17)
        self.assertEqual(rows[1]["initial"], 2)
        self.assertEqual(rows[1]["available"], 1)


if __name__ == "__main__":
    unittest.main()
