import unittest
from app.routes.legacy_migration import STATUS_MAP


class LegacyMigrationFoundationTests(unittest.TestCase):
    def test_terminal_legacy_states_are_preserved(self):
        self.assertEqual(STATUS_MAP["retire"], "delivered")
        self.assertEqual(STATUS_MAP["paye"], "delivered")
        self.assertEqual(STATUS_MAP["annule"], "cancelled")

    def test_pending_state_stays_open(self):
        self.assertEqual(STATUS_MAP["en_attente"], "received")


if __name__ == "__main__": unittest.main()
