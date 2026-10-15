"""One-shot destructive account lifecycle check using an isolated test company.

This script intentionally uses the configured database. It creates a uniquely
named owner, verifies reset and deletion through HTTP routes, and always tries
to remove the temporary owner in a finally block.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.model_reset_token import ResetToken  # noqa: E402
from app.models.model_user import User  # noqa: E402
from app.routes.auth import delete_own_account  # noqa: E402
from app.schemas.user_schema import DeleteAccountRequest  # noqa: E402


def _expect(response, status: int, step: str):
    if response.status_code != status:
        raise AssertionError(
            f"{step}: HTTP {response.status_code}, réponse={response.text[:500]}"
        )
    if not response.content:
        return None
    return response.json()


def _force_cleanup(email: str, password: str) -> None:
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == email).first()
        if owner is None:
            return
        delete_own_account(
            DeleteAccountRequest(
                password=password,
                confirmation="SUPPRIMER MON COMPTE",
            ),
            current_user=owner,
            db=db,
        )
    finally:
        db.close()


def main() -> int:
    marker = f"{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    email = f"tradecare-lifecycle-{marker}@example.com"
    password = f"TC-test-{uuid4().hex[:12]}!"
    company = f"Entreprise fictive Trade Care {marker}"
    category_name = f"Catégorie témoin {marker}"
    token = None
    report: list[dict[str, object]] = []

    # TestClient sans context manager n'exécute pas le scheduler de production.
    client = TestClient(app)
    try:
        registration = _expect(
            client.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": password,
                    "societe_ou_entreprise": company,
                    "devise": "XOF",
                    "interface_language": "fr",
                },
            ),
            200,
            "création du compte",
        )
        token = registration["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        report.append({"étape": "création", "résultat": "OK"})

        _expect(client.get("/auth/me", headers=headers), 200, "lecture du profil")
        report.append({"étape": "authentification", "résultat": "OK"})

        _expect(
            client.post(
                "/categories/",
                headers=headers,
                json={"nom": category_name, "description": "Donnée de contrôle"},
            ),
            200,
            "création de la donnée témoin",
        )
        categories = _expect(
            client.get("/categories/", headers=headers),
            200,
            "lecture de la donnée témoin",
        )
        if not any(item.get("nom") == category_name for item in categories):
            raise AssertionError("La catégorie témoin n'a pas été retrouvée")
        report.append({"étape": "donnée témoin", "résultat": "OK"})

        with patch("app.routes.reset.FastMail") as fast_mail:
            fast_mail.return_value.send_message = AsyncMock(return_value=None)
            _expect(
                client.post("/reset/request", headers=headers),
                200,
                "demande du code de réinitialisation",
            )

        db = SessionLocal()
        try:
            owner = db.query(User).filter(User.email == email).one()
            reset_token = (
                db.query(ResetToken)
                .filter(ResetToken.user_id == owner.id)
                .order_by(ResetToken.id.desc())
                .first()
            )
            if reset_token is None:
                raise AssertionError("Aucun code de réinitialisation enregistré")
            reset_code = reset_token.code
        finally:
            db.close()

        _expect(
            client.post(
                "/reset/verify",
                headers=headers,
                json={"code": reset_code},
            ),
            200,
            "validation de la réinitialisation",
        )
        categories = _expect(
            client.get("/categories/", headers=headers),
            200,
            "contrôle après réinitialisation",
        )
        if categories:
            raise AssertionError("Des catégories subsistent après la réinitialisation")
        _expect(
            client.get("/auth/me", headers=headers),
            200,
            "compte conservé après réinitialisation",
        )
        report.append(
            {
                "étape": "réinitialisation",
                "résultat": "OK — donnée effacée, compte conservé",
            }
        )

        _expect(
            client.request(
                "DELETE",
                "/auth/me",
                headers=headers,
                json={
                    "password": "mot-de-passe-incorrect",
                    "confirmation": "SUPPRIMER MON COMPTE",
                },
            ),
            400,
            "refus du mauvais mot de passe",
        )
        _expect(
            client.get("/auth/me", headers=headers),
            200,
            "session conservée après mauvais mot de passe",
        )
        report.append(
            {"étape": "mauvais mot de passe", "résultat": "refusé correctement"}
        )

        _expect(
            client.request(
                "DELETE",
                "/auth/me",
                headers=headers,
                json={
                    "password": password,
                    "confirmation": "SUPPRIMER MON COMPTE",
                },
            ),
            200,
            "suppression définitive",
        )
        _expect(
            client.get("/auth/me", headers=headers),
            401,
            "ancien jeton après suppression",
        )

        db = SessionLocal()
        try:
            if db.query(User).filter(User.email == email).first() is not None:
                raise AssertionError("Le compte temporaire existe encore en base")
        finally:
            db.close()
        report.append(
            {"étape": "suppression", "résultat": "OK — compte introuvable"}
        )

        print(json.dumps({"compte_test": email, "contrôles": report}, ensure_ascii=False, indent=2))
        return 0
    finally:
        _force_cleanup(email, password)
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
