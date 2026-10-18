from urllib.parse import urljoin, urlparse
from pathlib import Path

from app.config import settings


def public_url(path: str | None) -> str:
    """Retourne une URL publique sans modifier les chemins déjà absolus."""
    if not path:
        return ""
    if path.startswith(("http://", "https://", "data:", "file:")):
        return path

    base_url = settings.PUBLIC_BASE_URL.rstrip("/") + "/"
    return urljoin(base_url, path.lstrip("/"))


def document_asset_url(path: str | None) -> str:
    """Résout les médias locaux sans rappeler l'API pendant un rendu PDF."""
    if not path:
        return ""

    normalized = path.replace("\\", "/")
    if normalized.startswith("/static/"):
        upload_root = Path(__file__).resolve().parents[2] / "upload"
        local_path = upload_root / normalized.removeprefix("/static/")
        if local_path.is_file():
            return local_path.resolve().as_uri()

        public_host = (urlparse(settings.PUBLIC_BASE_URL).hostname or "").lower()
        if public_host in {"127.0.0.1", "localhost"}:
            return ""

    return public_url(path)
