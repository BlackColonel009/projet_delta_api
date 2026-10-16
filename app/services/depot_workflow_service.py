from __future__ import annotations

from dataclasses import dataclass


LEGACY_INITIAL_STATUS = "en_attente"

CANONICAL_STATUSES = {
    "recu",
    "stocke",
    "pret_retrait",
    "retire",
    "facture",
    "paye",
    "annule",
}

_ALIASES = {
    "en_attente": "recu",
    "facture_creee": "facture",
}

_ALLOWED_TRANSITIONS = {
    "recu": {"stocke", "pret_retrait", "retire", "annule"},
    "stocke": {"pret_retrait", "retire", "annule"},
    "pret_retrait": {"stocke", "retire", "annule"},
    "retire": {"facture", "paye"},
    "facture": {"paye"},
    "paye": set(),
    "annule": {"recu"},
}


class InvalidDepositTransition(ValueError):
    pass


def canonical_deposit_status(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    normalized = _ALIASES.get(normalized, normalized)
    if normalized not in CANONICAL_STATUSES:
        raise InvalidDepositTransition(f"Statut de dépôt inconnu : {status!r}")
    return normalized


@dataclass(frozen=True)
class DepositTransition:
    current: str
    target: str


def validate_deposit_transition(
    current_status: str | None,
    target_status: str,
) -> DepositTransition:
    current = canonical_deposit_status(current_status)
    target = canonical_deposit_status(target_status)
    if current == target:
        raise InvalidDepositTransition(
            f"Le dépôt est déjà dans l'état « {target} »."
        )
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidDepositTransition(
            f"Transition impossible de « {current} » vers « {target} »."
        )
    return DepositTransition(current=current, target=target)

