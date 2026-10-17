"""Shared conversion of invoice totals to words."""

from num2words import num2words


_CURRENCY_LABELS = {
    "fr": {
        "FCFA": "francs CFA",
        "XOF": "francs CFA",
        "EUR": "euros",
        "€": "euros",
        "USD": "dollars américains",
        "$": "dollars américains",
        "GBP": "livres sterling",
        "£": "livres sterling",
        "JPY": "yens",
        "¥": "yens",
        "CAD": "dollars canadiens",
        "AUD": "dollars australiens",
        "CHF": "francs suisses",
        "CNY": "yuans chinois",
        "INR": "roupies indiennes",
        "RUB": "roubles russes",
        "BRL": "réals brésiliens",
        "ZAR": "rands sud-africains",
    },
    "en": {
        "FCFA": "CFA francs",
        "XOF": "CFA francs",
        "EUR": "euros",
        "€": "euros",
        "USD": "US dollars",
        "$": "US dollars",
        "GBP": "pounds sterling",
        "£": "pounds sterling",
        "JPY": "yen",
        "¥": "yen",
        "CAD": "Canadian dollars",
        "AUD": "Australian dollars",
        "CHF": "Swiss francs",
        "CNY": "Chinese yuan",
        "INR": "Indian rupees",
        "RUB": "Russian rubles",
        "BRL": "Brazilian reals",
        "ZAR": "South African rand",
    },
}


def amount_to_words(amount: float, currency: str = "XOF", language: str = "fr") -> str:
    """Return a robust, localized amount-in-words label for invoices."""

    normalized_language = "en" if str(language).lower().startswith("en") else "fr"
    normalized_currency = str(currency or "XOF").upper()
    try:
        words = num2words(round(float(amount or 0), 2), lang=normalized_language)
        currency_label = _CURRENCY_LABELS[normalized_language].get(
            normalized_currency,
            currency or "XOF",
        )
        return f"{words.capitalize()} {currency_label}"
    except (TypeError, ValueError, NotImplementedError):
        return f"{float(amount or 0):.2f} {currency or 'XOF'}"
