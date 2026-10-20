import re


REPORT_LIST_STYLES = {
    "numbered", "dash", "dot", "bullet", "arrow", "check", "plain"
}
DEFAULT_REPORT_LIST_STYLE = "numbered"

_EXISTING_PREFIX = re.compile(
    r"^\s*(?:(?:\d+\s*[-.)])|[-.•·→✓])\s*"
)


def normalize_report_list_style(value: str | None) -> str:
    return value if value in REPORT_LIST_STYLES else DEFAULT_REPORT_LIST_STYLE


def format_work_report(content: str, style: str | None) -> str:
    """Formate chaque ligne non vide sans empiler les préfixes à l'édition."""
    selected_style = normalize_report_list_style(style)
    item_index = 0
    formatted: list[str] = []

    for raw_line in content.strip().splitlines():
        text = _EXISTING_PREFIX.sub("", raw_line).strip()
        if not text:
            if formatted and formatted[-1] != "":
                formatted.append("")
            continue

        item_index += 1
        prefix = {
            "numbered": f"{item_index} - ",
            "dash": "- ",
            "dot": ". ",
            "bullet": "• ",
            "arrow": "→ ",
            "check": "✓ ",
            "plain": "",
        }[selected_style]
        formatted.append(f"{prefix}{text}")

    while formatted and formatted[-1] == "":
        formatted.pop()
    return "\n".join(formatted)
