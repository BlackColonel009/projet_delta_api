import unittest

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401
from app.database import Base
from app.models.model_categorie import Categorie
from app.models.model_enterprise import Enterprise
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from app.services.enterprise_service import (
    create_owner_foundation,
    enterprise_scope_filter,
)


class EnterpriseCoreScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.owner = User(
            email="scope@example.com",
            password_hash="test-only",
            is_main_user=True,
            societe_ou_entreprise="Scope Group",
        )
        self.db.add(self.owner)
        self.db.flush()
        self.group, self.primary = create_owner_foundation(self.db, self.owner)
        self.annex = Enterprise(
            group_id=self.group.id,
            name="Annexe",
            code="annexe",
            currency="XOF",
        )
        self.db.add(self.annex)
        self.db.commit()
        self.owner.is_main_user = True

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _activate(self, enterprise: Enterprise):
        self.owner.active_enterprise_id = enterprise.id
        self.owner.active_enterprise_is_primary = enterprise.is_primary

    def test_same_category_name_is_allowed_in_different_enterprises(self):
        self.db.add_all(
            [
                Categorie(
                    nom="Ordinateurs",
                    user_id=self.owner.id,
                    enterprise_id=self.primary.id,
                ),
                Categorie(
                    nom="Ordinateurs",
                    user_id=self.owner.id,
                    enterprise_id=self.annex.id,
                ),
            ]
        )
        self.db.commit()
        self.assertEqual(self.db.query(Categorie).count(), 2)

    def test_category_name_is_case_insensitive_inside_one_enterprise(self):
        self.db.add(
            Categorie(
                nom="Phones",
                user_id=self.owner.id,
                enterprise_id=self.primary.id,
            )
        )
        self.db.commit()
        self.db.add(
            Categorie(
                nom="PHONES",
                user_id=self.owner.id,
                enterprise_id=self.primary.id,
            )
        )
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_annex_cannot_read_primary_or_legacy_rows(self):
        self.db.add_all(
            [
                Categorie(
                    nom="Primaire",
                    user_id=self.owner.id,
                    enterprise_id=self.primary.id,
                ),
                Categorie(
                    nom="Annexe",
                    user_id=self.owner.id,
                    enterprise_id=self.annex.id,
                ),
                Categorie(
                    nom="Historique",
                    user_id=self.owner.id,
                    enterprise_id=None,
                ),
            ]
        )
        self.db.commit()

        self._activate(self.annex)
        annex_names = {
            row.nom
            for row in self.db.query(Categorie).filter(
                enterprise_scope_filter(Categorie, self.owner)
            )
        }
        self.assertEqual(annex_names, {"Annexe"})

        self._activate(self.primary)
        primary_names = {
            row.nom
            for row in self.db.query(Categorie).filter(
                enterprise_scope_filter(Categorie, self.owner)
            )
        }
        self.assertEqual(primary_names, {"Primaire", "Historique"})

    def test_same_manufacturer_barcode_is_allowed_between_enterprises(self):
        primary_category = Categorie(
            nom="P1",
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
        )
        annex_category = Categorie(
            nom="P2",
            user_id=self.owner.id,
            enterprise_id=self.annex.id,
        )
        self.db.add_all([primary_category, annex_category])
        self.db.flush()
        primary_product = Produit(
            nom="Produit principal",
            categorie_id=primary_category.id,
            prix_achat=1,
            prix_vente=2,
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
        )
        annex_product = Produit(
            nom="Produit annexe",
            categorie_id=annex_category.id,
            prix_achat=1,
            prix_vente=2,
            user_id=self.owner.id,
            enterprise_id=self.annex.id,
        )
        self.db.add_all([primary_product, annex_product])
        self.db.flush()
        self.db.add_all(
            [
                UniteProduit(
                    produit_id=primary_product.id,
                    enterprise_id=self.primary.id,
                    tracabilite="TRACE-PRIMARY",
                    code_barre="123456789",
                ),
                UniteProduit(
                    produit_id=annex_product.id,
                    enterprise_id=self.annex.id,
                    tracabilite="TRACE-ANNEX",
                    code_barre="123456789",
                ),
            ]
        )
        self.db.commit()
        self.assertEqual(self.db.query(UniteProduit).count(), 2)


if __name__ == "__main__":
    unittest.main()
