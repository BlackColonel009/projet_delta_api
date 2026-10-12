import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.routes.rapport import delete_rapport
from app.schemas.rapport_schema import RapportCreate


class _FakeQuery:
    def __init__(self, result):
        self.result = result
        self.filters = []

    def filter(self, *filters):
        self.filters.extend(filters)
        return self

    def first(self):
        return self.result


class _FakeDb:
    def __init__(self, result):
        self.query_result = _FakeQuery(result)
        self.deleted = []
        self.commits = 0

    def query(self, *_args):
        return self.query_result

    def delete(self, value):
        self.deleted.append(value)

    def commit(self):
        self.commits += 1


class RapportTests(unittest.TestCase):
    def test_content_is_trimmed(self):
        data = RapportCreate(contenu="  Rapport valide  ")
        self.assertEqual(data.contenu, "Rapport valide")

    def test_blank_content_is_rejected(self):
        with self.assertRaises(ValueError):
            RapportCreate(contenu="   ")

    def test_subuser_cannot_delete_another_subusers_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=7)
        db = _FakeDb(report)
        current_subuser = SimpleNamespace(
            id=5,
            parent_user_id=42,
            is_main_user=False,
        )

        with self.assertRaises(HTTPException) as caught:
            delete_rapport(9, db=db, current_user=current_subuser)

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(db.deleted, [])
        self.assertEqual(db.commits, 0)

    def test_subuser_can_delete_own_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=5)
        db = _FakeDb(report)
        current_subuser = SimpleNamespace(
            id=5,
            parent_user_id=42,
            is_main_user=False,
        )

        result = delete_rapport(9, db=db, current_user=current_subuser)

        self.assertEqual(result["message"], "Rapport supprimé avec succès")
        self.assertEqual(db.deleted, [report])
        self.assertEqual(db.commits, 1)

    def test_main_user_can_moderate_company_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=5)
        db = _FakeDb(report)
        admin = SimpleNamespace(id=42, is_main_user=True)

        delete_rapport(9, db=db, current_user=admin)

        self.assertEqual(db.deleted, [report])
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
