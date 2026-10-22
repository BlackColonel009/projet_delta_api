import unittest
from datetime import datetime
from types import SimpleNamespace

from app.email.branded_templates import (
    client_welcome_email,
    loyalty_email,
    payment_reminder_email,
    product_recommendation_email,
    subscription_request_admin_email,
    subscription_request_decision_email,
)
from app.utils.public_url import public_url


class BrandedEmailTemplateTests(unittest.TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            societe_ou_entreprise="Delta & Fils",
            email="contact@delta.test",
            logo_entreprise="/static/logos/delta.png",
            facture_color="#0F766E",
            devise="XOF",
            interface_language="fr",
        )

    def test_payment_reminder_is_branded_and_escapes_customer_data(self):
        html = payment_reminder_email(
            user=self.user,
            client_name="Achille <script>",
            order_id=42,
            product_names=["Ordinateur & écran"],
            total=250000,
            paid=100000,
            balance=150000,
            currency="XOF",
            order_date=datetime(2026, 10, 12),
            delay_days=7,
        )

        self.assertIn("Delta &amp; Fils", html)
        self.assertIn("Achille &lt;script&gt;", html)
        self.assertNotIn("Achille <script>", html)
        self.assertIn("150 000,00 XOF", html)
        self.assertIn(public_url("/static/logos/delta.png"), html)

    def test_loyalty_email_lists_purchased_products(self):
        html = loyalty_email(
            user=self.user,
            client_name="Ama",
            product_names=["Imprimante", "Cartouche"],
        )
        self.assertIn("Imprimante", html)
        self.assertIn("Cartouche", html)
        self.assertIn("Merci pour votre achat", html)

    def test_client_welcome_email_uses_company_logo_and_warm_message(self):
        html = client_welcome_email(
            user=self.user,
            client_name="Ama <VIP>",
        )
        self.assertIn("Bienvenue Ama &lt;VIP&gt;", html)
        self.assertIn("Nous serons plus que ravis", html)
        self.assertIn("Delta &amp; Fils", html)
        self.assertIn(public_url("/static/logos/delta.png"), html)

    def test_recommendation_contains_product_and_pdf_explanation(self):
        product = SimpleNamespace(
            nom="PC Pro",
            image_url="https://cdn.test/pc.jpg",
            caracteristiques="16 Go RAM",
            commentaire=None,
            prix_vente=475000,
        )
        html = product_recommendation_email(
            user=self.user,
            client_name="Kossi",
            product=product,
        )
        self.assertIn("PC Pro", html)
        self.assertIn("16 Go RAM", html)
        self.assertIn("475 000,00 XOF", html)
        self.assertIn("jointe à cet email au format PDF", html)

    def test_subscription_request_email_is_personalized_and_escaped(self):
        plan = SimpleNamespace(name="Diamant <Pro>")
        request = SimpleNamespace(
            billing_cycle="annual",
            current_plan_code="classic",
            requested_plan_code="diamond",
            quoted_amount=480000,
            currency="XOF",
            note="Besoin pour 12 employés & 3 agences",
        )

        html = subscription_request_admin_email(
            requester=self.user,
            plan=plan,
            request=request,
        )

        self.assertIn("Nouvelle demande de mise à niveau", html)
        self.assertIn("Diamant &lt;Pro&gt;", html)
        self.assertIn("12 employés &amp; 3 agences", html)
        self.assertNotIn("Diamant <Pro>", html)

    def test_subscription_decision_contains_superadmin_response(self):
        plan = SimpleNamespace(name="Or")
        request = SimpleNamespace(
            billing_cycle="monthly",
            requested_plan_code="gold",
            quoted_amount=25000,
            currency="XOF",
            admin_note="Votre accès est prêt & actif.",
        )

        html = subscription_request_decision_email(
            company=self.user,
            plan=plan,
            request=request,
            approved=True,
        )

        self.assertIn("Votre demande a été approuvée", html)
        self.assertIn("Votre accès est prêt &amp; actif.", html)
        self.assertIn("25 000,00 XOF", html)

    def test_customer_emails_follow_saved_english_language(self):
        self.user.interface_language = "en"
        html = loyalty_email(
            user=self.user,
            client_name="Ama",
            product_names=["Printer"],
        )
        self.assertIn("Thank you for your purchase", html)
        self.assertIn("Customer care", html)
        self.assertNotIn("Merci pour votre achat", html)

    def test_superadmin_email_uses_recipient_language(self):
        recipient = SimpleNamespace(interface_language="en")
        plan = SimpleNamespace(name="Diamond")
        request = SimpleNamespace(
            billing_cycle="annual",
            current_plan_code="classic",
            requested_plan_code="diamond",
            quoted_amount=480000,
            currency="XOF",
            note=None,
        )
        html = subscription_request_admin_email(
            requester=self.user,
            recipient=recipient,
            plan=plan,
            request=request,
        )
        self.assertIn("New upgrade request", html)
        self.assertIn("Action required", html)


if __name__ == "__main__":
    unittest.main()
