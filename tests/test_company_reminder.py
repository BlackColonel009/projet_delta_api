import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

from app.routes.notification import (
    get_company_daily_reminder,
    trigger_company_alarm_test,
    update_company_alarm_sound,
    update_company_daily_reminder,
)
from app.schemas.notification_schema import (
    CompanyAlarmSoundUpdate,
    CompanyReminderUpdate,
)


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
        self.added = None

    def query(self, *_args):
        return _FakeQuery(self.owner)

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        self.refreshed = value

    def add(self, value):
        self.added = value
        value.id = 91
        value.created_at = datetime(2026, 10, 14, 12, 0, 0)


def _owner():
    return SimpleNamespace(
        id=42,
        is_main_user=True,
        daily_report_reminder_enabled=False,
        daily_report_reminder_hour=18,
        daily_report_reminder_minute=0,
        daily_report_reminder_revision=0,
        daily_report_reminder_updated_at=None,
        daily_report_alarm_sound="signature",
        daily_report_alarm_sound_revision=0,
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
        self.assertEqual(result["sound_id"], "signature")

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

    def test_main_user_can_send_alarm_test_to_company(self):
        owner = _owner()
        owner.username = "Direction"
        owner.email = "direction@example.com"
        db = _FakeDb(owner)

        result = trigger_company_alarm_test(db=db, current_user=owner)

        self.assertEqual(result["event_id"], 91)
        self.assertEqual(result["requested_by"], "Direction")
        self.assertEqual(result["trigger_at"], "2026-10-14T12:00:05Z")
        self.assertEqual(result["expires_at"], "2026-10-14T12:02:00Z")
        self.assertEqual(db.added.parent_user_id, owner.id)
        self.assertTrue(db.added.is_read)
        self.assertEqual(db.commits, 1)

    def test_main_user_applies_alarm_sound_to_company(self):
        owner = _owner()
        db = _FakeDb(owner)

        result = update_company_alarm_sound(
            CompanyAlarmSoundUpdate(sound_id="urgent"),
            db=db,
            current_user=owner,
        )

        self.assertEqual(result["sound_id"], "urgent")
        self.assertEqual(result["sound_revision"], 1)
        self.assertEqual(result["revision"], 1)
        self.assertEqual(db.commits, 1)

    def test_subuser_admin_cannot_apply_company_alarm_sound(self):
        owner = _owner()
        db = _FakeDb(owner)
        admin = SimpleNamespace(
            id=8,
            is_main_user=False,
            parent_user_id=42,
            role="admin",
        )

        with self.assertRaises(HTTPException) as caught:
            update_company_alarm_sound(
                CompanyAlarmSoundUpdate(sound_id="soft"),
                db=db,
                current_user=admin,
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(db.commits, 0)

    def test_non_admin_subuser_cannot_send_alarm_test(self):
        owner = _owner()
        db = _FakeDb(owner)
        subuser = SimpleNamespace(
            id=7,
            is_main_user=False,
            parent_user_id=42,
            role="Caissier(e)",
        )

        with self.assertRaises(HTTPException) as caught:
            trigger_company_alarm_test(db=db, current_user=subuser)

        self.assertEqual(caught.exception.status_code, 403)
        self.assertIsNone(db.added)


if __name__ == "__main__":
    unittest.main()
