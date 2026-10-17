import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401
from app.database import Base
from app.models.model_commande import CommandeVente
from app.models.model_depense import Depense
from app.models.model_facture import Facture, TypeFacture
from app.models.model_paiement import Paiement
from app.models.model_client import Client
from app.models.model_enterprise import Enterprise
from app.models.model_user import User
from app.services.enterprise_service import (
    create_owner_foundation,
    enterprise_scope_filter,
)


class EnterpriseCommerceScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.owner = User(
            email="commerce-scope@example.com",
            password_hash="test-only",
            is_main_user=True,
            societe_ou_entreprise="Commerce Scope",
        )
        self.db.add(self.owner)
        self.db.flush()
        self.group, self.primary = create_owner_foundation(self.db, self.owner)
        self.annex = Enterprise(
            group_id=self.group.id,
            name="Annexe Commerce",
            code="annexe-commerce",
            currency="XOF",
        )
        self.db.add(self.annex)
        self.db.flush()
        self.primary_client = Client(
            nom="Client siege",
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
        )
        self.annex_client = Client(
            nom="Client annexe",
            user_id=self.owner.id,
            enterprise_id=self.annex.id,
        )
        self.db.add_all([self.primary_client, self.annex_client])
        self.db.flush()
        self.primary_sale = CommandeVente(
            client_id=self.primary_client.id,
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
            total_ttc=100,
        )
        self.annex_sale = CommandeVente(
            client_id=self.annex_client.id,
            user_id=self.owner.id,
            enterprise_id=self.annex.id,
            total_ttc=200,
        )
        self.db.add_all([self.primary_sale, self.annex_sale])
        self.db.flush()
        self.primary_invoice = Facture(
            type=TypeFacture.vente,
            commande_id=self.primary_sale.id,
            client_id=self.primary_client.id,
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
            total_ttc=100,
        )
        self.annex_invoice = Facture(
            type=TypeFacture.vente,
            commande_id=self.annex_sale.id,
            client_id=self.annex_client.id,
            user_id=self.owner.id,
            enterprise_id=self.annex.id,
            total_ttc=200,
        )
        self.db.add_all([self.primary_invoice, self.annex_invoice])
        self.db.flush()
        self.db.add_all(
            [
                Paiement(
                    facture_id=self.primary_invoice.id,
                    montant=50,
                    user_id=self.owner.id,
                    enterprise_id=self.primary.id,
                ),
                Paiement(
                    facture_id=self.annex_invoice.id,
                    montant=75,
                    user_id=self.owner.id,
                    enterprise_id=self.annex.id,
                ),
                Depense(
                    libelle="Siege",
                    montant=10,
                    user_id=self.owner.id,
                    enterprise_id=self.primary.id,
                ),
                Depense(
                    libelle="Annexe",
                    montant=20,
                    user_id=self.owner.id,
                    enterprise_id=self.annex.id,
                ),
                Depense(
                    libelle="Historique",
                    montant=5,
                    user_id=self.owner.id,
                    enterprise_id=None,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _activate(self, enterprise):
        self.owner.active_enterprise_id = enterprise.id
        self.owner.active_enterprise_is_primary = enterprise.is_primary

    def test_annex_only_sees_its_commerce_and_finance_rows(self):
        self._activate(self.annex)
        self.assertEqual(
            [row.id for row in self.db.query(CommandeVente).filter(
                enterprise_scope_filter(CommandeVente, self.owner)
            )],
            [self.annex_sale.id],
        )
        self.assertEqual(
            [row.id for row in self.db.query(Facture).filter(
                enterprise_scope_filter(Facture, self.owner)
            )],
            [self.annex_invoice.id],
        )
        self.assertEqual(
            [row.libelle for row in self.db.query(Depense).filter(
                enterprise_scope_filter(Depense, self.owner)
            )],
            ["Annexe"],
        )

    def test_primary_keeps_legacy_null_rows_but_not_annex_rows(self):
        self._activate(self.primary)
        labels = {
            row.libelle
            for row in self.db.query(Depense).filter(
                enterprise_scope_filter(Depense, self.owner)
            )
        }
        self.assertEqual(labels, {"Siege", "Historique"})

    def test_payment_scope_follows_its_invoice_enterprise(self):
        self._activate(self.annex)
        payment_ids = {
            row.id
            for row in self.db.query(Paiement).filter(
                enterprise_scope_filter(Paiement, self.owner)
            )
        }
        self.assertEqual(payment_ids, {self.annex_invoice.paiements[0].id})


if __name__ == "__main__":
    unittest.main()
