import pytest

from app.services.depot_workflow_service import (
    InvalidDepositTransition,
    canonical_deposit_status,
    validate_deposit_transition,
)


def test_legacy_initial_status_is_compatible():
    assert canonical_deposit_status("en_attente") == "recu"
    transition = validate_deposit_transition("en_attente", "stocke")
    assert transition.current == "recu"
    assert transition.target == "stocke"


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("recu", "pret_retrait"),
        ("stocke", "pret_retrait"),
        ("pret_retrait", "retire"),
        ("retire", "facture"),
        ("facture", "paye"),
        ("annule", "recu"),
    ],
)
def test_valid_transitions(current, target):
    assert validate_deposit_transition(current, target).target == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("paye", "annule"),
        ("retire", "stocke"),
        ("annule", "retire"),
        ("stocke", "paye"),
        ("recu", "recu"),
    ],
)
def test_invalid_transitions(current, target):
    with pytest.raises(InvalidDepositTransition):
        validate_deposit_transition(current, target)

