"""Helpers for invoice-only product descriptions and characteristics."""

import json
from typing import Any


def parse_characteristics(value: Any) -> dict[str, str] | str:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except (TypeError, ValueError):
            return stripped
        if isinstance(parsed, dict):
            return {str(key): str(item) for key, item in parsed.items()}
        return str(parsed)
    return str(value)


def serialize_characteristics(value: Any) -> str:
    parsed = parse_characteristics(value)
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False)
    return parsed


def invoice_line_characteristics(line) -> dict[str, str] | str:
    """Prefer the immutable/editable invoice snapshot over the product record."""

    snapshot = getattr(line, "caracteristiques_snapshot", None)
    if snapshot is not None:
        return parse_characteristics(snapshot)
    product = getattr(line, "produit", None)
    return parse_characteristics(
        getattr(product, "caracteristiques", None) if product else None
    )
