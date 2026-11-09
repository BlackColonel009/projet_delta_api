import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.unite_produit import lier_barcodes_a_produit
from app.services.unit_reassignment_service import attach_reusable_unit


class _FakeQuery:
    def __init__(self, first_result=None, count_result=0):
        self._first_result = first_result
        self._count_result = count_result

    def filter(self, *args):
        return self

    def first(self):
        return self._first_result

    def count(self):
        return self._count_result


class _FakeDb:
    def __init__(self, query_results):
        self._query_results = list(query_results)
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    def query(self, _model):
        return self._query_results.pop(0)

    def add(self, instance):
        self.added.append(instance)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _FakeUnitModel:
    code_barre = None
    tracabilite = None
    enterprise_id = None
    produit_id = None
    statut = None

    def __new__(cls, **values):
        return SimpleNamespace(**values)


class BarcodeAssociationTests(unittest.TestCase):
    def test_reactivates_unavailable_unit_on_same_product(self):
        product = SimpleNamespace(id=10, nom="Produit")
        unit = SimpleNamespace(
            produit_id=10,
            produit=product,
            enterprise_id=1,
            statut="indisponible",
            date_modification=None,
        )

        result = attach_reusable_unit(unit, product, enterprise_id=1)

        self.assertEqual(result.action, "reactivated")
        self.assertEqual(unit.statut, "disponible")

    def test_never_moves_sold_unit(self):
        old_product = SimpleNamespace(id=99, nom="Ancienne fiche")
        target_product = SimpleNamespace(id=10, nom="Nouvelle fiche")
        unit = SimpleNamespace(
            produit_id=99,
            produit=old_product,
            enterprise_id=1,
            statut="vendu",
            date_modification=None,
        )

        result = attach_reusable_unit(unit, target_product, enterprise_id=1)

        self.assertEqual(result.action, "conflict")
        self.assertEqual(unit.produit_id, 99)
        self.assertEqual(unit.statut, "vendu")

    @patch("app.routes.unite_produit.UniteProduit", _FakeUnitModel)
    @patch("app.routes.unite_produit.log_action")
    def test_creates_missing_unit_and_attaches_temporary_unit(self, _log_action):
        product = SimpleNamespace(
            id=10,
            nom="Produit test",
            quantite=3,
            a_des_barcodes=False,
            date_modification=None,
        )
        temporary_unit = SimpleNamespace(
            produit_id=None,
            enterprise_id=1,
            statut="temp",
            date_creation=None,
            date_modification=None,
        )
        db = _FakeDb(
            [
                _FakeQuery(first_result=product),
                _FakeQuery(first_result=None),
                _FakeQuery(first_result=temporary_unit),
                _FakeQuery(count_result=5),
            ]
        )

        result = lier_barcodes_a_produit(
            produit_id=10,
            barcodes=["CODE-1", "CODE-2", "CODE-1"],
            db=db,
            current_user=SimpleNamespace(
                id=4,
                is_main_user=True,
                active_enterprise_id=1,
            ),
        )

        self.assertEqual(result["added_count"], 2)
        self.assertEqual(len(db.added), 1)
        self.assertEqual(temporary_unit.produit_id, 10)
        self.assertEqual(temporary_unit.statut, "disponible")
        self.assertIsNotNone(temporary_unit.date_creation)
        self.assertEqual(product.quantite, 5)
        self.assertTrue(product.a_des_barcodes)
        self.assertEqual(db.commits, 1)

    @patch("app.routes.unite_produit.log_action")
    @patch("app.routes.unite_produit.UniteProduit", _FakeUnitModel)
    def test_rejects_code_already_owned_by_another_product(self, _log_action):
        product = SimpleNamespace(
            id=10,
            nom="Produit test",
            quantite=1,
            a_des_barcodes=False,
            date_modification=None,
        )
        conflicting_unit = SimpleNamespace(
            produit_id=99,
            enterprise_id=1,
            statut="disponible",
        )
        db = _FakeDb(
            [
                _FakeQuery(first_result=product),
                _FakeQuery(first_result=conflicting_unit),
            ]
        )

        with self.assertRaises(HTTPException) as raised:
            lier_barcodes_a_produit(
                produit_id=10,
                barcodes=["CODE-CONFLIT"],
                db=db,
                current_user=SimpleNamespace(
                    id=4,
                    is_main_user=True,
                    active_enterprise_id=1,
                ),
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(db.commits, 0)

    @patch("app.routes.unite_produit.log_action")
    @patch("app.routes.unite_produit.UniteProduit", _FakeUnitModel)
    def test_moves_unavailable_unit_from_another_product(self, _log_action):
        target_product = SimpleNamespace(
            id=10,
            nom="Bonne fiche",
            quantite=0,
            a_des_barcodes=False,
            date_modification=None,
        )
        old_product = SimpleNamespace(
            id=99,
            nom="Mauvaise fiche",
            quantite=1,
            date_modification=None,
        )
        unavailable_unit = SimpleNamespace(
            produit_id=99,
            produit=old_product,
            enterprise_id=1,
            statut="indisponible",
            date_creation=None,
            date_modification=None,
            commande_vente_id=None,
        )
        db = _FakeDb(
            [
                _FakeQuery(first_result=target_product),
                _FakeQuery(first_result=unavailable_unit),
                _FakeQuery(count_result=0),
                _FakeQuery(first_result=old_product),
                _FakeQuery(count_result=1),
            ]
        )

        result = lier_barcodes_a_produit(
            produit_id=10,
            barcodes=["CODE-DEPLACE"],
            db=db,
            current_user=SimpleNamespace(
                id=4,
                is_main_user=True,
                active_enterprise_id=1,
            ),
        )

        self.assertEqual(unavailable_unit.produit_id, 10)
        self.assertEqual(unavailable_unit.statut, "disponible")
        self.assertEqual(old_product.quantite, 0)
        self.assertEqual(target_product.quantite, 1)
        self.assertEqual(result["moved_codes"], ["CODE-DEPLACE"])
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
