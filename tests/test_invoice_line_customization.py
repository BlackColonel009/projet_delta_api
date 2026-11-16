import unittest
from types import SimpleNamespace

from app.models.model_facture import LigneFacture
from app.schemas.facture_schema import InvoiceCustomLineCreate
from app.services.invoice_line_snapshot_service import (
    invoice_line_characteristics,
    parse_characteristics,
    serialize_characteristics,
)


class InvoiceLineCustomizationTests(unittest.TestCase):
    def test_model_has_invoice_only_characteristics_snapshot(self):
        self.assertIn("caracteristiques_snapshot", LigneFacture.__table__.columns)

    def test_snapshot_has_priority_over_product_characteristics(self):
        line = SimpleNamespace(
            caracteristiques_snapshot='{"Couleur": "Noir"}',
            produit=SimpleNamespace(
                caracteristiques='{"Couleur": "Blanc", "RAM": "8 Go"}'
            ),
        )
        self.assertEqual(
            invoice_line_characteristics(line),
            {"Couleur": "Noir"},
        )

    def test_empty_snapshot_can_hide_product_characteristics(self):
        line = SimpleNamespace(
            caracteristiques_snapshot="{}",
            produit=SimpleNamespace(caracteristiques='{"RAM": "8 Go"}'),
        )
        self.assertEqual(invoice_line_characteristics(line), {})

    def test_unicode_round_trip(self):
        value = {"Mémoire": "16 Go", "État": "Très bon"}
        self.assertEqual(parse_characteristics(serialize_characteristics(value)), value)

    def test_custom_line_schema_accepts_invoice_only_product(self):
        line = InvoiceCustomLineCreate(
            description="Transport exceptionnel",
            quantite=3,
            unite="service",
            prix_unitaire=2500,
        )
        self.assertEqual(line.quantite * line.prix_unitaire, 7500)
        self.assertEqual(line.unite, "service")


if __name__ == "__main__":
    unittest.main()
