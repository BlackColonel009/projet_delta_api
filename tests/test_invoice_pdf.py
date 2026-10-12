import os
from types import SimpleNamespace
import unittest

from app.services.generate_facture_from_commande import generate_facture_pdf


class ProfessionalInvoicePdfTests(unittest.TestCase):
    def test_professional_pdf_is_generated_without_mutating_product_data(self):
        raw_characteristics = '{"Couleur": "Noir", "Capacite": "256 Go"}'
        product = SimpleNamespace(
            id=82,
            nom="Telephone Pro",
            caracteristiques=raw_characteristics,
        )
        line = SimpleNamespace(
            description="Telephone Pro",
            quantite=2,
            prix_unitaire=125000.0,
            total_ligne=250000.0,
            produit=product,
        )
        user = SimpleNamespace(
            devise="XOF",
            logo_entreprise=None,
            societe_ou_entreprise="Delta Distribution",
            email="contact@example.com",
            addresse="Lome",
            nif="NIF-001",
            tva=0.18,
            telephone="+228 90000000",
            facture_color="#5C6BC0",
        )
        client = SimpleNamespace(
            nom="Client Test",
            adresse="Lome",
            telephone="+228 91111111",
            email="client@example.com",
        )
        invoice = SimpleNamespace(
            id=14,
            type="vente",
            date_creation=SimpleNamespace(strftime=lambda _: "12/10/2026"),
            total_ht=250000.0,
            tva=45000.0,
            total_ttc=295000.0,
            commande_id=None,
            commande_achat_id=None,
            lignes=[line],
            user=user,
            sub_user=None,
            client=client,
            fournisseur=None,
        )

        pdf_path = generate_facture_pdf(invoice, db=SimpleNamespace())
        try:
            with open(pdf_path, "rb") as pdf_file:
                content = pdf_file.read()
            self.assertTrue(content.startswith(b"%PDF"))
            self.assertGreater(len(content), 2_000)
            self.assertEqual(product.caracteristiques, raw_characteristics)
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)


if __name__ == "__main__":
    unittest.main()
