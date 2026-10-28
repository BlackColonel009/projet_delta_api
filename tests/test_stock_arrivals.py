import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401 - enregistre tous les modèles SQLAlchemy
from app.database import Base
from app.models.model_categorie import Categorie
from app.models.model_enterprise import Enterprise
from app.models.model_produit import Produit
from app.models.model_stock_arrival import (
    StockArrival,
    StockArrivalLine,
    StockArrivalUnit,
)
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from app.routes.stock_arrival import (
    export_arrivals_report,
    link_existing_units_to_arrival,
    product_arrival_units,
    transfer_stock,
    validate_arrival,
)
from app.routes.produit import _with_available_quantities
from app.schemas.stock_arrival_schema import (
    StockArrivalExistingUnitsLink,
    StockTransferCreate,
    StockTransferItem,
)
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
        # Résoudre d'abord les identifiants : leur lecture peut rafraîchir la
        # session et effacer les attributs de contexte non persistés du test.
        primary_id = self.primary.id
        group_id = self.group.id
        self.owner.active_enterprise_id = primary_id
        self.owner.active_enterprise_is_primary = True
        self.owner.active_enterprise_business_type = "commerce"
        self.owner.enterprise_group_id = group_id

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

    def test_existing_stock_can_be_linked_without_duplication(self):
        retrospective = StockArrival(
            enterprise_id=self.primary.id,
            user_id=self.owner.id,
            name="Rattrapage ancien arrivage",
            created_by_name="Propriétaire",
        )
        self.db.add(retrospective)
        self.db.flush()
        units = [
            UniteProduit(
                produit_id=self.product.id,
                enterprise_id=self.primary.id,
                tracabilite=f"OLD-{index}",
                code_barre=f"OLD-{index}",
                statut="disponible" if index == 1 else "vendu",
            )
            for index in (1, 2)
        ]
        self.db.add_all(units)
        self.db.commit()

        line = link_existing_units_to_arrival(
            retrospective.id,
            StockArrivalExistingUnitsLink(
                product_id=self.product.id,
                barcodes=["OLD-1", "OLD-2"],
            ),
            self.db,
            self.owner,
        )
        self.assertEqual(line["quantity"], 2)
        self.assertEqual(line["qr_count"], 2)
        before = self.db.query(UniteProduit).count()

        validate_arrival(retrospective.id, self.db, self.owner)

        self.assertEqual(self.db.query(UniteProduit).count(), before)
        self.assertEqual(
            self.db.query(StockArrivalUnit)
            .join(StockArrivalLine)
            .filter(StockArrivalLine.arrival_id == retrospective.id)
            .count(),
            2,
        )

    def test_unknown_existing_barcode_does_not_create_arrival_line(self):
        retrospective = StockArrival(
            enterprise_id=self.primary.id,
            user_id=self.owner.id,
            name="Rattrapage invalide",
            created_by_name="Propriétaire",
        )
        self.db.add(retrospective)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            link_existing_units_to_arrival(
                retrospective.id,
                StockArrivalExistingUnitsLink(
                    product_id=self.product.id,
                    barcodes=["CODE-INCONNU"],
                ),
                self.db,
                self.owner,
            )
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            self.db.query(StockArrivalLine)
            .filter(StockArrivalLine.arrival_id == retrospective.id)
            .count(),
            0,
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

    def test_arrival_units_follow_sale_in_receiving_enterprise(self):
        validate_arrival(self.arrival.id, self.db, self.owner)
        transfer_stock(
            StockTransferCreate(
                destination_enterprise_id=self.annex.id,
                items=[StockTransferItem(product_id=self.product.id, quantity=1)],
                source_arrival_id=self.arrival.id,
            ),
            self.db,
            self.owner,
        )
        transferred_unit = self.db.query(UniteProduit).filter(
            UniteProduit.enterprise_id == self.annex.id,
        ).one()
        transferred_unit.statut = "vendu"
        self.db.commit()

        groups = product_arrival_units(self.product.id, self.db, self.owner)
        sold = next(
            unit
            for group in groups
            for unit in group["units"]
            if unit["id"] == transferred_unit.id
        )
        self.assertEqual(sold["status"], "vendu")
        self.assertTrue(sold["transferred"])
        self.assertEqual(sold["current_enterprise_name"], self.annex.name)

    def test_sold_unit_cannot_be_transferred(self):
        validate_arrival(self.arrival.id, self.db, self.owner)
        for unit in self.db.query(UniteProduit).filter(
            UniteProduit.produit_id == self.product.id,
        ):
            unit.statut = "vendu"
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            transfer_stock(
                StockTransferCreate(
                    destination_enterprise_id=self.annex.id,
                    items=[StockTransferItem(
                        product_id=self.product.id,
                        quantity=1,
                    )],
                    source_arrival_id=self.arrival.id,
                ),
                self.db,
                self.owner,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_product_badge_uses_available_units_not_stale_quantity(self):
        validate_arrival(self.arrival.id, self.db, self.owner)
        for unit in self.db.query(UniteProduit).filter(
            UniteProduit.produit_id == self.product.id,
        ):
            unit.statut = "vendu"
        # Simule l'ancienne valeur qui produisait « Stock faible » à tort.
        self.product.quantite = 1
        self.db.flush()

        result = _with_available_quantities(self.db, [self.product])
        self.assertEqual(result[0].quantite, 0)

    def test_arrivals_report_is_a_valid_pdf_response(self):
        validate_arrival(self.arrival.id, self.db, self.owner)
        self._activate_primary()
        response = export_arrivals_report(None, None, self.db, self.owner)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertGreater(len(response.body), 2000)


if __name__ == "__main__":
    unittest.main()
