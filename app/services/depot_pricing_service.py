"""Règles tarifaires déterministes du service de consigne."""

from dataclasses import dataclass


MODE_UNITAIRE = "unitaire"
MODE_DUREE = "duree"


def normalize_pricing_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    aliases = {
        "unitaire": MODE_UNITAIRE,
        "unité": MODE_UNITAIRE,
        "unite": MODE_UNITAIRE,
        "duree": MODE_DUREE,
        "durée": MODE_DUREE,
        "minute": MODE_DUREE,
        "minutes": MODE_DUREE,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Mode de tarification invalide : {value}") from exc


@dataclass(frozen=True)
class DepositLinePrice:
    mode: str
    unit_price: float
    quantity: int
    duration_minutes: int | None
    total: float


def calculate_deposit_line(
    *,
    mode: str,
    quantity: int,
    unit_price: float | int | None,
    price_per_minute: float | int | None,
    custom_price: float | int | None = None,
    duration_minutes: int | None = None,
) -> DepositLinePrice:
    """Calcule une ligne sans dépendre de SQLAlchemy ou de l'interface."""
    canonical_mode = normalize_pricing_mode(mode)
    if quantity < 1:
        raise ValueError("La quantité doit être supérieure à zéro.")
    if duration_minutes is not None and duration_minutes < 0:
        raise ValueError("La durée ne peut pas être négative.")

    if custom_price is not None:
        rate = float(custom_price)
    elif canonical_mode == MODE_UNITAIRE:
        rate = float(unit_price or 0)
    else:
        rate = float(price_per_minute or 0)
    if rate < 0:
        raise ValueError("Le tarif ne peut pas être négatif.")

    if canonical_mode == MODE_DUREE and custom_price is None:
        billed_duration = duration_minutes or 0
        total = rate * billed_duration * quantity
    else:
        billed_duration = duration_minutes if canonical_mode == MODE_DUREE else None
        total = rate * quantity

    return DepositLinePrice(
        mode=canonical_mode,
        unit_price=round(rate, 6),
        quantity=quantity,
        duration_minutes=billed_duration,
        total=round(total, 2),
    )
