"""Small server-side i18n helpers for background documents and messages."""

SUPPORTED_LANGUAGES = {"fr", "en"}


def normalize_language(value: object | None) -> str:
    language = str(value or "fr").lower().split("-")[0]
    return language if language in SUPPORTED_LANGUAGES else "fr"


def language_of(user: object | None) -> str:
    return normalize_language(getattr(user, "interface_language", None))


def translated(language: str, french: str, english: str) -> str:
    return english if normalize_language(language) == "en" else french


def user_text(user: object | None, french: str, english: str) -> str:
    return translated(language_of(user), french, english)
