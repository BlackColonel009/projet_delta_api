from urllib.parse import urljoin

from app.config import settings


def public_url(path: str | None) -> str:
    """Retourne une URL publique sans modifier les chemins déjà absolus."""
    if not path:
        return ""
    if path.startswith(("http://", "https://", "data:", "file:")):
        return path

    base_url = settings.PUBLIC_BASE_URL.rstrip("/") + "/"
    return urljoin(base_url, path.lstrip("/"))
