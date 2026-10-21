import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401 - enregistre tous les modèles SQLAlchemy
from app.database import Base
from app.models.model_categorie import Categorie
from app.models.model_enterprise import Enterprise
from app.models.model_produit import Produit
from app.models.model_stock_arrival import StockArrival, StockArrivalLine
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from app.routes.stock_arrival import transfer_stock, validate_arrival
from app.schemas.stock_arrival_schema import StockTransferCreate, StockTransferItem
from app.services.enterprise_service import create_owner_foundation


class StockArrivalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.owner = User(
            email="arrivals@example.com",
            password_hash="test-only",
            is_main_user=True,
            societe_ou_entreprise="Trade Care Test",
        )
        self.db.add(self.owner)
        self.db.flush()
        self.group, self.primary = create_owner_foundation(self.db, self.owner)
        self.annex = Enterprise(
            group_id=self.group.id,
            name="Annexe Commerce",
            code="annexe-arrivages",
            business_type="commerce",
            currency="XOF",
        )
        self.db.add(self.annex)
        self.db.flush()
        self.category = Categorie(
            nom="Téléphones",
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
        )
        self.db.add(self.category)
        self.db.flush()
        self.product = Produit(
            nom="Trade Phone",
            categorie_id=self.category.id,
            prix_achat=100,
            prix_vente=150,
            quantite=0,
            user_id=self.owner.id,
            enterprise_id=self.primary.id,
        )
        self.db.add(self.product)
        self.db.flush()
        self.arrival = StockArrival(
            enterprise_id=self.primary.id,
            user_id=self.owner.id,
            name="Réception octobre",
            created_by_name="Propriétaire",
        )
        self.db.add(self.arrival)
        self.db.flush()
        self.db.add(
            StockArrivalLine(
                arrival_id=self.arrival.id,
                enterprise_id=self.primary.id,
                product_id=self.product.id,
                quantity=2,
                barcodes_json=["BAR-001"],
            )
        )
        self.db.commit()
        self._activate_primary()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _activate_primary(self):
        self.owner.active_enterprise_id = self.primary.id
        self.owner.active_enterprise_is_primary = True
        self.owner.active_enterprise_business_type = "commerce"
        self.owner.enterprise_group_id = self.group.id

    def test_validation_adds_units_only_once(self):
        result = validate_arrival(self.arrival.id, self.db, self.owner)
        self.assertEqual(result["arrival_id"], self.arrival.id)
        self.assertEqual(
            self.db.query(UniteProduit).filter(
                UniteProduit.produit_id == self.product.id
            ).count(),
            2,
        )
        self.db.refresh(self.product)
        self.assertEqual(self.product.quantite, 2)
        self.assertEqual(
            self.db.query(StockArrival).get(self.arrival.id).status,
            "validated",
        )

    def test_transfer_moves_units_and_creates_linked_product(self):
        validate_arrival(self.arrival.id, self.db, self.owner)
        result = transfer_stock(
            StockTransferCreate(
                destination_enterprise_id=self.annex.id,
                items=[StockTransferItem(product_id=self.product.id, quantity=1)],
                source_arrival_id=self.arrival.id,
            ),
            self.db,
            self.owner,
        )
        self.assertIsNotNone(result["transfer_id"])
        source_count = self.db.query(UniteProduit).filter(
            UniteProduit.enterprise_id == self.primary.id,
            UniteProduit.produit_id == self.product.id,
            UniteProduit.statut == "disponible",
        ).count()
        destination_product = self.db.query(Produit).filter(
            Produit.enterprise_id == self.annex.id,
            Produit.catalog_key == self.product.catalog_key,
        ).one()
        destination_count = self.db.query(UniteProduit).filter(
            UniteProduit.enterprise_id == self.annex.id,
            UniteProduit.produit_id == destination_product.id,
            UniteProduit.statut == "disponible",
        ).count()
        self.assertEqual(source_count, 1)
        self.assertEqual(destination_count, 1)
        self.assertEqual(self.product.quantite, 1)
        self.assertEqual(destination_product.quantite, 1)


if __name__ == "__main__":
    unittest.main()
