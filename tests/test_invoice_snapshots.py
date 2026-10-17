import unittest
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401 - register every related model
from app.database import Base
from app.models.model_enterprise import Enterprise, EnterpriseGroup
from app.models.model_user import SubUser, User
from app.models.model_facture import TypeFacture
from app.services.invoice_snapshot_service import (
    invoice_snapshot_values,
    validate_official_invoice_date,
)
from app.services.invoice_template_registry import (
    PROFESSIONAL_TEMPLATES,
    SIMPLE_TEMPLATES,
    serialized_catalog,
    validate_template_code,
)
from app.services.simple_invoice_renderer import render_simple_invoice
from app.services.generate_facture_from_commande import generate_facture_pdf


class InvoiceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.owner = User(
            email="invoice-owner@example.com",
            password_hash="test-only",
            username="Direction Delta",
            is_main_user=True,
            facture_color="#224466",
        )
        self.db.add(self.owner)
        self.db.flush()
        group = EnterpriseGroup(
            owner_user_id=self.owner.id,
            name="Groupe Factures",
        )
        self.db.add(group)
        self.db.flush()
        self.enterprise = Enterprise(
            group_id=group.id,
            name="Boutique Centrale",
            code="boutique-centrale",
            is_primary=True,
            enterprise_type="principale",
            invoice_color="#113355",
            simple_invoice_template="simple_classic",
            professional_invoice_template="professional_signature",
        )
        self.db.add(self.enterprise)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_owner_identity_and_enterprise_design_are_snapshotted(self):
        values = invoice_snapshot_values(
            self.db,
            self.owner,
            self.enterprise.id,
        )

        self.assertEqual(values["issued_by_user_id"], self.owner.id)
        self.assertIsNone(values["issued_by_sub_user_id"])
        self.assertEqual(values["issuer_name_snapshot"], "Direction Delta")
        self.assertEqual(values["issuer_role_snapshot"], "Propriétaire")
        self.assertEqual(values["invoice_color_snapshot"], "#113355")

    def test_collaborator_name_and_role_are_snapshotted(self):
        collaborator = SubUser(
            username="Afi Mensah",
            password_hash="test-only",
            role="Commercial(e)",
            parent_user_id=self.owner.id,
        )
        self.db.add(collaborator)
        self.db.commit()

        values = invoice_snapshot_values(
            self.db,
            collaborator,
            self.enterprise.id,
        )

        self.assertIsNone(values["issued_by_user_id"])
        self.assertEqual(values["issued_by_sub_user_id"], collaborator.id)
        self.assertEqual(values["issuer_name_snapshot"], "Afi Mensah")
        self.assertEqual(values["issuer_role_snapshot"], "Commercial(e)")

    def test_manual_date_accepts_past_and_rejects_future(self):
        past = datetime.now(timezone.utc) - timedelta(days=3)
        resolved = validate_official_invoice_date(past)
        self.assertIsNone(resolved.tzinfo)

        with self.assertRaises(HTTPException) as context:
            validate_official_invoice_date(
                datetime.now(timezone.utc) + timedelta(days=1)
            )
        self.assertEqual(context.exception.detail["code"], "INVALID_INVOICE_DATE")

    def test_template_registry_has_required_stable_catalog(self):
        self.assertEqual(len(SIMPLE_TEMPLATES), 3)
        self.assertEqual(len(PROFESSIONAL_TEMPLATES), 8)
        self.assertEqual(
            validate_template_code("simple_compact", "simple"),
            "simple_compact",
        )
        with self.assertRaises(ValueError):
            validate_template_code("professional_signature", "simple")

        catalog = serialized_catalog()
        self.assertEqual(len(catalog["simple"]), 3)
        self.assertEqual(len(catalog["professional"]), 8)

    def test_three_simple_templates_generate_valid_multipage_ready_pdfs(self):
        line = SimpleNamespace(
            produit=None,
            description="Maintenance préventive",
            quantite=2,
            prix_unitaire=12500.0,
            total_ligne=25000.0,
        )
        client = SimpleNamespace(
            nom="Client Pilote",
            adresse="Lomé",
            telephone="+228 90000000",
        )
        for template_code in (
            "simple_classic",
            "simple_compact",
            "simple_receipt",
        ):
            facture = SimpleNamespace(
                id=42,
                type=TypeFacture.vente,
                date_creation=datetime(2026, 10, 16, 9, 30),
                user=self.owner,
                client=client,
                fournisseur=None,
                commande_id=None,
                lignes=[line] * 45,
                paiements=[],
                total_ht=25000.0 * 45,
                total_ttc=26500.0 * 45,
                tva=6.0,
                invoice_color_snapshot="#113355",
                simple_template_snapshot=template_code,
                issuer_name_snapshot="Direction Delta",
                issuer_role_snapshot="Propriétaire",
            )
            rendered = render_simple_invoice(facture, self.db, self.owner)
            self.assertTrue(rendered.getvalue().startswith(b"%PDF"))
            self.assertGreater(len(rendered.getvalue()), 3000)

    def test_eight_professional_templates_generate_valid_pdfs(self):
        line = SimpleNamespace(
            produit=None,
            description="Installation et configuration",
            quantite=1,
            prix_unitaire=75000.0,
            total_ligne=75000.0,
        )
        client = SimpleNamespace(
            nom="Client Entreprise",
            adresse="Lomé",
            telephone="+228 90000000",
            email="client@example.com",
        )
        for definition in PROFESSIONAL_TEMPLATES:
            facture = SimpleNamespace(
                id=84,
                type=TypeFacture.vente,
                date_creation=datetime(2026, 10, 16, 10, 0),
                user=self.owner,
                sub_user=None,
                client=client,
                fournisseur=None,
                commande_id=None,
                commande_achat_id=None,
                lignes=[line] * 4,
                total_ht=300000.0,
                total_ttc=318000.0,
                tva=6.0,
                invoice_color_snapshot="#113355",
                professional_template_snapshot=definition.code,
                issuer_name_snapshot="Direction Delta",
                issuer_role_snapshot="Propriétaire",
            )
            path = generate_facture_pdf(facture, self.db)
            try:
                with open(path, "rb") as generated:
                    content = generated.read()
                self.assertTrue(content.startswith(b"%PDF"), definition.code)
                self.assertGreater(len(content), 3000, definition.code)
            finally:
                if os.path.exists(path):
                    os.remove(path)


if __name__ == "__main__":
    unittest.main()
