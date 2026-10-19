import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.rapport import (
    _report_is_mine,
    delete_rapport,
    get_report_sharing_settings,
    update_rapport,
    update_report_sharing_settings,
)
from app.schemas.rapport_schema import (
    RapportCreate,
    RapportSharingUpdate,
    RapportUpdate,
)


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
        self.added = []
        self.refreshed = []

    def query(self, *_args):
        return self.query_result

    def delete(self, value):
        self.deleted.append(value)

    def commit(self):
        self.commits += 1

    def add(self, value):
        self.added.append(value)

    def refresh(self, value):
        self.refreshed.append(value)


class RapportTests(unittest.TestCase):
    def test_content_is_trimmed(self):
        data = RapportCreate(contenu="  Rapport valide  ")
        self.assertEqual(data.contenu, "Rapport valide")

    def test_blank_content_is_rejected(self):
        with self.assertRaises(ValueError):
            RapportCreate(contenu="   ")

    def test_report_ownership_is_a_boolean(self):
        report = SimpleNamespace(
            source="manual",
            user_id=42,
            sub_user_id=None,
        )
        admin = SimpleNamespace(id=42, is_main_user=True)

        ownership = _report_is_mine(report, admin)

        self.assertIsInstance(ownership, bool)
        self.assertTrue(ownership)

    def test_subuser_cannot_delete_another_subusers_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=7, source="manual")
        db = _FakeDb(report)
        current_subuser = SimpleNamespace(
            id=5,
            parent_user_id=42,
            is_main_user=False,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )

        with self.assertRaises(HTTPException) as caught:
            delete_rapport(9, db=db, current_user=current_subuser)

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(db.deleted, [])
        self.assertEqual(db.commits, 0)

    def test_subuser_can_delete_own_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=5, source="manual")
        db = _FakeDb(report)
        current_subuser = SimpleNamespace(
            id=5,
            parent_user_id=42,
            is_main_user=False,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )

        result = delete_rapport(9, db=db, current_user=current_subuser)

        self.assertEqual(result["message"], "Rapport supprimé avec succès")
        self.assertEqual(db.deleted, [report])
        self.assertEqual(db.commits, 1)

    def test_main_user_can_moderate_company_report(self):
        report = SimpleNamespace(id=9, user_id=42, sub_user_id=5, source="manual")
        db = _FakeDb(report)
        admin = SimpleNamespace(id=42, is_main_user=True, active_enterprise_id=1, active_enterprise_is_primary=True)

        delete_rapport(9, db=db, current_user=admin)

        self.assertEqual(db.deleted, [report])
        self.assertEqual(db.commits, 1)

    def test_report_can_only_be_edited_on_publication_day(self):
        report = SimpleNamespace(
            id=9,
            user_id=42,
            sub_user_id=None,
            contenu="Ancien contenu",
            date_creation=datetime.utcnow() - timedelta(days=1),
            date_modification=None,
            user=None,
            sub_user=None,
            source="manual",
        )
        db = _FakeDb(report)
        admin = SimpleNamespace(
            id=42,
            email="admin@example.com",
            username="Admin",
            avatar_url=None,
            is_main_user=True,
            is_superuser=False,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )

        with self.assertRaises(HTTPException) as caught:
            update_rapport(
                9,
                RapportUpdate(contenu="Nouveau contenu"),
                db=db,
                current_user=admin,
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(report.contenu, "Ancien contenu")
        self.assertEqual(db.commits, 0)

    def test_same_day_edit_is_saved_and_added_to_history(self):
        admin = SimpleNamespace(
            id=42,
            email="admin@example.com",
            username="Admin",
            avatar_url=None,
            is_main_user=True,
            is_superuser=False,
            active_enterprise_id=1,
            active_enterprise_is_primary=True,
        )
        report = SimpleNamespace(
            id=9,
            user_id=42,
            sub_user_id=None,
            contenu="Ancien contenu",
            date_creation=datetime.utcnow(),
            date_modification=None,
            user=admin,
            sub_user=None,
            source="manual",
        )
        db = _FakeDb(report)

        with patch("app.routes.rapport.log_action") as history_log:
            result = update_rapport(
                9,
                RapportUpdate(contenu="Nouveau contenu"),
                db=db,
                current_user=admin,
            )

        self.assertEqual(result["contenu"], "Nouveau contenu")
        self.assertTrue(result["is_edited"])
        self.assertIsNotNone(report.date_modification)
        self.assertEqual(db.commits, 1)
        history_log.assert_called_once()
        details = history_log.call_args.kwargs["details"]
        self.assertIn("Ancien contenu", details)
        self.assertIn("Nouveau contenu", details)

    def test_main_user_controls_company_report_sharing(self):
        owner = SimpleNamespace(
            id=42,
            is_main_user=True,
            is_superuser=False,
            report_sharing_enabled=True,
        )
        db = _FakeDb(owner)

        result = update_report_sharing_settings(
            RapportSharingUpdate(enabled=False),
            db=db,
            current_user=owner,
        )

        self.assertFalse(result["enabled"])
        self.assertTrue(result["can_manage"])
        self.assertEqual(db.commits, 1)

    def test_company_member_reads_sharing_setting_but_cannot_change_it(self):
        owner = SimpleNamespace(
            id=42,
            is_main_user=True,
            report_sharing_enabled=False,
        )
        db = _FakeDb(owner)
        member = SimpleNamespace(
            id=7,
            is_main_user=False,
            is_superuser=False,
            parent_user_id=42,
        )

        current = get_report_sharing_settings(db=db, current_user=member)
        self.assertFalse(current["enabled"])
        self.assertFalse(current["can_manage"])

        with self.assertRaises(HTTPException) as caught:
            update_report_sharing_settings(
                RapportSharingUpdate(enabled=True),
                db=db,
                current_user=member,
            )
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
