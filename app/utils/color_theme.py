import re


def _normalize_hex(value: str | None, fallback: str) -> str:
    candidate = (value or fallback).strip().lstrip("#")
    if len(candidate) == 3:
        candidate = "".join(character * 2 for character in candidate)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", candidate):
        candidate = fallback.strip().lstrip("#")
    return f"#{candidate.upper()}"


def _mix(color: str, target: tuple[int, int, int], ratio: float) -> str:
    value = color.lstrip("#")
    source = tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    mixed = tuple(
        round(channel + (target_channel - channel) * ratio)
        for channel, target_channel in zip(source, target)
    )
    return "#" + "".join(f"{channel:02X}" for channel in mixed)


def build_document_palette(
    color: str | None,
    fallback: str = "#7A2CBF",
) -> dict[str, str]:
    primary = _normalize_hex(color, fallback)
    red, green, blue = (
        int(primary[index : index + 2], 16) for index in (1, 3, 5)
    )
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return {
        "primary": primary,
        "primary_dark": _mix(primary, (0, 0, 0), 0.28),
        "primary_soft": _mix(primary, (255, 255, 255), 0.82),
        "primary_pale": _mix(primary, (255, 255, 255), 0.94),
        "on_primary": "#241A29" if luminance > 0.66 else "#FFFFFF",
    }
