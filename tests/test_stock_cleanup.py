import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.unite_produit import (
    STOCK_CLEANUP_CONFIRMATION,
    cleanup_company_stock,
    preview_stock_cleanup,
)
from app.schemas.unite_produit_schema import StockCleanupRequest


class _FakeQuery:
    def __init__(self, *, rows=None, scalar_value=None, deleted=0, count_value=0):
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.deleted = deleted
        self.count_value = count_value
        self.filters = []

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *args):
        self.filters.extend(args)
        return self

    def group_by(self, *_args):
        return self

    def all(self):
        return self.rows

    def scalar(self):
        return self.scalar_value

    def delete(self, **_kwargs):
        return self.deleted

    def count(self):
        return self.count_value


class _FakeDb:
    def __init__(self, queries):
        self.queries = list(queries)
        self.used_queries = []
        self.commits = 0
        self.rollbacks = 0
        self.added = []

    def query(self, *_args):
        query = self.queries.pop(0)
        self.used_queries.append(query)
        return query

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def add(self, value):
        self.added.append(value)


class StockCleanupTests(unittest.TestCase):
    def setUp(self):
        self.admin = SimpleNamespace(
            id=42,
            is_main_user=True,
            email="admin@example.com",
        )

    def test_preview_separates_deletable_and_protected_units(self):
        db = _FakeDb(
            [
                _FakeQuery(
                    rows=[
                        ("disponible", 7),
                        ("indisponible", 3),
                        ("vendu", 11),
                        ("en cours", 2),
                    ]
                ),
                _FakeQuery(scalar_value=4),
            ]
        )

        result = preview_stock_cleanup(db=db, current_user=self.admin)

        self.assertEqual(result["eligible_count"], 10)
        self.assertEqual(result["protected_count"], 13)
        self.assertEqual(result["affected_products"], 4)

    def test_cleanup_rejects_missing_confirmation(self):
        with self.assertRaises(HTTPException) as caught:
            cleanup_company_stock(
                StockCleanupRequest(confirmation="oui"),
                db=_FakeDb([]),
                current_user=self.admin,
            )

        self.assertEqual(caught.exception.status_code, 400)

    def test_cleanup_never_includes_sold_or_in_progress_units(self):
        units = [
            SimpleNamespace(id=1, produit_id=10, statut="disponible"),
            SimpleNamespace(id=2, produit_id=10, statut="indisponible"),
            SimpleNamespace(id=3, produit_id=10, statut="vendu"),
            SimpleNamespace(id=4, produit_id=10, statut="en cours"),
        ]
        product = SimpleNamespace(id=10, quantite=99, date_modification=None)
        delete_query = _FakeQuery(deleted=2)
        db = _FakeDb(
            [
                _FakeQuery(rows=units),
                delete_query,
                _FakeQuery(rows=[product]),
                _FakeQuery(count_value=0),
            ]
        )

        with patch("app.routes.unite_produit.log_action"):
            result = cleanup_company_stock(
                StockCleanupRequest(confirmation=STOCK_CLEANUP_CONFIRMATION),
                db=db,
                current_user=self.admin,
            )

        id_filters = [
            expression
            for expression in delete_query.filters
            if getattr(getattr(expression, "left", None), "name", None) == "id"
        ]
        self.assertEqual(list(id_filters[0].right.value), [1, 2])
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(result["available_count"], 1)
        self.assertEqual(result["unavailable_count"], 1)
        self.assertEqual(product.quantite, 0)
        self.assertEqual(db.rollbacks, 0)


if __name__ == "__main__":
    unittest.main()
