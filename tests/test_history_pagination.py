from datetime import datetime
from types import SimpleNamespace
import unittest

from app.main import app as _app  # Charge tous les modèles SQLAlchemy liés.
from app.routes.historique_general import list_historiques


class _HistoryQuery:
    def __init__(self, rows):
        self.rows = rows
        self.offset_value = 0
        self.limit_value = len(rows)

    def options(self, *args):
        return self

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        end = self.offset_value + self.limit_value
        return self.rows[self.offset_value:end]


class _HistoryDb:
    def __init__(self, rows):
        self.query_result = _HistoryQuery(rows)

    def query(self, *args):
        return self.query_result


class HistoryPaginationTests(unittest.TestCase):
    def test_company_history_is_paginated_and_exposes_author(self):
        admin = SimpleNamespace(email="admin@example.com")
        employee = SimpleNamespace(username="Afi")
        rows = [
            SimpleNamespace(
                id=index,
                action=f"Action {index}",
                type_entite="produit",
                entite_id=index,
                details="Détail",
                date_action=datetime(2026, 10, 12, 8, index),
                user=admin,
                sub_user=employee if index == 3 else None,
            )
            for index in range(1, 6)
        ]
        db = _HistoryDb(rows)
        current_user = SimpleNamespace(
            id=9,
            is_main_user=True,
            parent_user_id=None,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )

        result = list_historiques(
            page=2,
            limit=2,
            start=None,
            end=None,
            type_entite=None,
            db=db,
            current_user=current_user,
        )

        self.assertEqual([item["id"] for item in result], [3, 4])
        self.assertEqual(result[0]["done_by"], "Afi")
        self.assertEqual(result[0]["actor_type"], "Employé")
        self.assertEqual(result[1]["done_by"], "admin@example.com")
        self.assertEqual(result[1]["actor_type"], "Administrateur")
        self.assertEqual(db.query_result.offset_value, 2)
        self.assertEqual(db.query_result.limit_value, 2)


if __name__ == "__main__":
    unittest.main()
