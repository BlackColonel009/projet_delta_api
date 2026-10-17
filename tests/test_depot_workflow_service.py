import unittest

from app.services.depot_workflow_service import (
    InvalidDepositTransition,
    canonical_deposit_status,
    validate_deposit_transition,
)


class DepotWorkflowServiceTests(unittest.TestCase):
    def test_legacy_initial_status_is_compatible(self):
        self.assertEqual(canonical_deposit_status("en_attente"), "recu")
        transition = validate_deposit_transition("en_attente", "stocke")
        self.assertEqual(transition.current, "recu")
        self.assertEqual(transition.target, "stocke")

    def test_valid_transitions(self):
        cases = [
            ("recu", "pret_retrait"),
            ("stocke", "pret_retrait"),
            ("pret_retrait", "retire"),
            ("retire", "facture"),
            ("facture", "paye"),
            ("annule", "recu"),
        ]
        for current, target in cases:
            with self.subTest(current=current, target=target):
                self.assertEqual(
                    validate_deposit_transition(current, target).target,
                    target,
                )

    def test_invalid_transitions(self):
        cases = [
            ("paye", "annule"),
            ("retire", "stocke"),
            ("annule", "retire"),
            ("stocke", "paye"),
            ("recu", "recu"),
        ]
        for current, target in cases:
            with self.subTest(current=current, target=target):
                with self.assertRaises(InvalidDepositTransition):
                    validate_deposit_transition(current, target)


if __name__ == "__main__":
    unittest.main()

