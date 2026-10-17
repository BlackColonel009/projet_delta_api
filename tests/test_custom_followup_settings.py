import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.models.model_clientfollowup import FollowupStatus
from app.models.model_facture import TypeFacture
from app.routes.followup import (
    update_client_followup_settings,
    update_invoice_payment_reminder,
)
from app.schemas.followup_schema import (
    ClientFollowupSettingsUpdate,
    PaymentReminderSettingsUpdate,
)


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args):
        return self

    def first(self):
        return self.result

    def all(self):
        return self.result


class _Db:
    def __init__(self, *results):
        self.results = list(results)
        self.commits = 0

    def query(self, *_args):
        return _Query(self.results.pop(0))

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        return None


def _main_user():
    return SimpleNamespace(
        id=11,
        is_main_user=True,
        active_enterprise_id=101,
        active_enterprise_is_primary=True,
    )


class CustomFollowupSettingsTests(unittest.TestCase):
    @patch("app.routes.followup.log_action")
    def test_invoice_setting_only_reschedules_its_payment_followup(self, _log):
        invoice = SimpleNamespace(
            id=7,
            user_id=11,
            type=TypeFacture.vente,
            commande_id=41,
            date_creation=datetime(2026, 10, 1, 9, 0),
        )
        followup = SimpleNamespace(
            id=9,
            date_achat=datetime(2026, 10, 2, 9, 0),
            date_prochain_envoi=None,
            dernier_envoi=datetime(2026, 10, 3, 9, 0),
            delai_avant_relance=2,
            payment_reminder_enabled=True,
        )
        db = _Db(invoice, followup)

        result = update_invoice_payment_reminder(
            7,
            PaymentReminderSettingsUpdate(
                enabled=False,
                start_after_days=7,
            ),
            db=db,
            current_user=_main_user(),
        )

        self.assertFalse(result["enabled"])
        self.assertEqual(result["start_after_days"], 7)
        self.assertEqual(
            followup.date_prochain_envoi,
            datetime(2026, 10, 9, 9, 0),
        )
        self.assertIsNone(followup.dernier_envoi)
        self.assertEqual(db.commits, 1)

    @patch("app.routes.followup.log_action")
    def test_client_setting_updates_existing_pending_workflow(self, _log):
        client = SimpleNamespace(id=4, user_id=11)
        followup = SimpleNamespace(
            date_achat=datetime(2026, 10, 10, 8, 0),
            statut=FollowupStatus.en_attente,
            date_prochain_envoi=None,
        )
        db = _Db(client, [followup])

        result = update_client_followup_settings(
            4,
            ClientFollowupSettingsUpdate(
                enabled=True,
                thank_you_delay_days=3,
                recommendations_enabled=True,
                first_recommendation_delay_days=12,
                recommendation_interval_days=30,
            ),
            db=db,
            current_user=_main_user(),
        )

        self.assertTrue(result["enabled"])
        self.assertEqual(result["recommendation_interval_days"], 30)
        self.assertEqual(
            followup.date_prochain_envoi,
            datetime(2026, 10, 13, 8, 0),
        )
        self.assertEqual(db.commits, 1)


if __name__ == "__main__":
    unittest.main()
