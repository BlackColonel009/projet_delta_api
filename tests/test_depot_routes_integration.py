import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app as production_app  # importe et enregistre tous les modèles
from app.models.model_client import Client
from app.models.model_depot import Depot
from app.models.model_depot_service import DepotService
from app.models.model_facture_depot import FactureDepot
from app.models.model_user import User
from app.routes import depot as depot_routes
from app.routes import facture_depot as facture_depot_routes
from app.schemas.depot_schema import DepotCancellation, DepotRestore
from app.schemas.facture_depot_schema import FactureDepotPaymentCreate


class DepotRoutesIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False)
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self):
        self.db = self.Session()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()
        owner = User(
            id=1,
            email="owner@example.test",
            password_hash="not-used",
            is_main_user=True,
        )
        client = Client(id=1, nom="Client test", user_id=1)
        service = DepotService(
            id=1,
            nom="Consigne",
            mode_tarification="unitaire",
            user_id=1,
        )
        depot = Depot(
            id=1,
            client_id=1,
            service_id=1,
            description_bien="Colis test",
            statut="en_attente",
            prix_total=2500,
            user_id=1,
        )
        facture = FactureDepot(
            id=1,
            depot_id=1,
            client_id=1,
            montant_ht=2500,
            tva=0,
            montant_ttc=2500,
            statut="en_attente",
            user_id=1,
        )
        self.db.add_all([owner, client, service, depot, facture])
        self.db.commit()

        self.current_user = SimpleNamespace(
            id=1,
            email="owner@example.test",
            is_main_user=True,
            is_superuser=False,
            parent_user_id=None,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )

    def tearDown(self):
        self.db.close()

    def test_complete_controlled_lifecycle_and_payment(self):
        depot_routes.stocker_depot(1, self.db, self.current_user)
        depot_routes.marquer_depot_pret_retrait(1, self.db, self.current_user)
        depot_routes.annuler_depot(
            1,
            DepotCancellation(motif="Demande du client"),
            self.db,
            self.current_user,
        )
        depot_routes.restaurer_depot(
            1,
            DepotRestore(motif="Client revenu"),
            self.db,
            self.current_user,
        )
        depot_routes.retirer_depot(1, self.db, self.current_user)
        facture_depot_routes.payer_facture_depot(
            1,
            FactureDepotPaymentCreate(mode_paiement="Espèces"),
            self.db,
            self.current_user,
        )

        self.db.expire_all()
        depot = self.db.get(Depot, 1)
        facture = self.db.get(FactureDepot, 1)
        self.assertEqual(depot.statut, "paye")
        self.assertIsNotNone(depot.date_stockage)
        self.assertIsNotNone(depot.date_pret_retrait)
        self.assertIsNotNone(depot.date_retrait)
        self.assertEqual(facture.statut, "payee")
        self.assertEqual(facture.mode_paiement, "Espèces")
        self.assertIsNotNone(facture.date_paiement)

    def test_cannot_reopen_paid_deposit(self):
        depot = self.db.get(Depot, 1)
        depot.statut = "paye"
        self.db.commit()
        with self.assertRaises(HTTPException) as raised:
            depot_routes.annuler_depot(
                1,
                DepotCancellation(motif="Annulation tardive"),
                self.db,
                self.current_user,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_other_company_cannot_change_deposit(self):
        self.current_user = SimpleNamespace(
            id=2,
            email="other@example.test",
            is_main_user=True,
            is_superuser=False,
            parent_user_id=None,
            active_enterprise_id=2,
            active_enterprise_is_primary=True,
        )
        with self.assertRaises(HTTPException) as raised:
            depot_routes.stocker_depot(1, self.db, self.current_user)
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
