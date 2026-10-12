import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.routes.notification import (
    get_company_daily_reminder,
    update_company_daily_reminder,
)
from app.schemas.notification_schema import CompanyReminderUpdate


class _FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def first(self):
        return self.result


class _FakeDb:
    def __init__(self, owner):
        self.owner = owner
        self.commits = 0
        self.refreshed = None

    def query(self, *_args):
        return _FakeQuery(self.owner)

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        self.refreshed = value


def _owner():
    return SimpleNamespace(
        id=42,
        is_main_user=True,
        daily_report_reminder_enabled=False,
        daily_report_reminder_hour=18,
        daily_report_reminder_minute=0,
        daily_report_reminder_revision=0,
        daily_report_reminder_updated_at=None,
    )


class CompanyReminderTests(unittest.TestCase):
    def test_company_member_reads_owner_schedule(self):
        owner = _owner()
        subuser = SimpleNamespace(
            id=7,
            is_main_user=False,
            parent_user_id=42,
            role="Technicien(ne)",
        )

        result = get_company_daily_reminder(
            db=_FakeDb(owner),
            current_user=subuser,
        )

        self.assertEqual(result["hour"], 18)
        self.assertFalse(result["enabled"])

    def test_non_admin_subuser_cannot_change_schedule(self):
        owner = _owner()
        db = _FakeDb(owner)
        subuser = SimpleNamespace(
            id=7,
            is_main_user=False,
            parent_user_id=42,
            role="Caissier(e)",
        )

        with self.assertRaises(HTTPException) as caught:
            update_company_daily_reminder(
                CompanyReminderUpdate(enabled=True, hour=19, minute=30),
                db=db,
                current_user=subuser,
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(db.commits, 0)

    def test_admin_subuser_updates_schedule_for_company(self):
        owner = _owner()
        db = _FakeDb(owner)
        admin = SimpleNamespace(
            id=8,
            is_main_user=False,
            parent_user_id=42,
            role="admin",
        )

        result = update_company_daily_reminder(
            CompanyReminderUpdate(enabled=True, hour=20, minute=15),
            db=db,
            current_user=admin,
        )

        self.assertTrue(result["enabled"])
        self.assertEqual((result["hour"], result["minute"]), (20, 15))
        self.assertEqual(result["revision"], 1)
        self.assertEqual(db.commits, 1)
        self.assertIs(db.refreshed, owner)


if __name__ == "__main__":
    unittest.main()
