import unittest
from datetime import datetime
from types import SimpleNamespace

from app.email.branded_templates import payment_confirmation_email


def _company(language="fr"):
    return SimpleNamespace(
        interface_language=language,
        societe_ou_entreprise="Delta & Fils",
        email="contact@delta.example",
        logo_entreprise=None,
        facture_color="#0F766E",
    )


class BrandedPaymentEmailTests(unittest.TestCase):
    def test_paid_receipt_is_branded_and_escapes_customer_name(self):
        html = payment_confirmation_email(
            user=_company(),
            client_name="Client <Premium>",
            invoice_id=42,
            invoice_date=datetime(2026, 10, 16),
            payment_amount=15000,
            payment_method="Mobile Money",
            total=15000,
            paid=15000,
            balance=0,
            currency="FCFA",
            is_settled=True,
        )

        self.assertIn("<!doctype html>", html)
        self.assertIn("Delta &amp; Fils", html)
        self.assertIn("Client &lt;Premium&gt;", html)
        self.assertIn("Paiement confirmé", html)
        self.assertIn("Mobile Money", html)
        self.assertIn("aucun solde restant", html)

    def test_partial_receipt_uses_english_and_displays_balance(self):
        html = payment_confirmation_email(
            user=_company("en"),
            client_name="Alex",
            invoice_id=8,
            invoice_date=datetime(2026, 10, 16),
            payment_amount=2500,
            payment_method="Cash",
            total=10000,
            paid=2500,
            balance=7500,
            currency="XOF",
            is_settled=False,
        )

        self.assertIn("Payment confirmed", html)
        self.assertIn("Balance due", html)
        self.assertIn("7 500,00 XOF", html)
        self.assertIn("Partially paid", html)


if __name__ == "__main__":
    unittest.main()
