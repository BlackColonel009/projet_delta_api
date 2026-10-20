import re
import unicodedata


REPORT_LIST_STYLES = {
    "numbered", "dash", "dot", "bullet", "arrow", "check", "plain"
}
DEFAULT_REPORT_LIST_STYLE = "numbered"

_EXISTING_PREFIX = re.compile(
    r"^\s*(?:(?:\d+\s*[-.)])|[-.•·→✓])\s*"
)

_STRUCTURED_SECTION_TITLES = {
    "travail effectue",
    "work completed",
    "resultats obtenus",
    "results achieved",
    "difficultes rencontrees",
    "challenges encountered",
    "prochaines etapes",
    "next steps",
}


def _normalized_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_value.strip().lower().rstrip(":"))


def _prefix(item_index: int, style: str) -> str:
    return {
        "numbered": f"{item_index} - ",
        "dash": "- ",
        "dot": ". ",
        "bullet": "• ",
        "arrow": "→ ",
        "check": "✓ ",
        "plain": "",
    }[style]


def normalize_report_list_style(value: str | None) -> str:
    return value if value in REPORT_LIST_STYLES else DEFAULT_REPORT_LIST_STYLE


def format_work_report(content: str, style: str | None) -> str:
    """Formate les lignes métier sans numéroter l'objet ni les titres de section."""
    selected_style = normalize_report_list_style(style)
    lines = content.strip().splitlines()
    is_structured = any(
        _normalized_title(line) in _STRUCTURED_SECTION_TITLES for line in lines
    )
    if not is_structured:
        return content.strip()
    item_index = 0
    inside_section = False
    formatted: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        normalized = _normalized_title(stripped)

        if normalized in _STRUCTURED_SECTION_TITLES:
            formatted.append(stripped)
            inside_section = True
            item_index = 0
            continue

        if not stripped:
            if formatted and formatted[-1] != "":
                formatted.append("")
            continue

        # Dans le formulaire structuré, tout ce qui précède le premier titre
        # correspond à l'objet du rapport et reste volontairement intact.
        if not inside_section:
            formatted.append(stripped)
            continue

        text = _EXISTING_PREFIX.sub("", stripped).strip()
        item_index += 1
        formatted.append(f"{_prefix(item_index, selected_style)}{text}")

    while formatted and formatted[-1] == "":
        formatted.pop()
    return "\n".join(formatted)
