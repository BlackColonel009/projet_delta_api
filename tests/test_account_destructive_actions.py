import asyncio
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.routes.auth import delete_own_account
from app.routes.reset import request_reset_account, verify_reset_code
from app.schemas.user_schema import DeleteAccountRequest
from app.utils.security import require_main_user


class _FakeQuery:
    def filter(self, *_args):
        return self

    def delete(self, **_kwargs):
        return 1


class _FakeDb:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.added = []

    def query(self, *_args):
        return _FakeQuery()

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class AccountDestructiveActionTests(unittest.TestCase):
    def test_all_destructive_routes_require_main_user(self):
        for route, parameter in (
            (delete_own_account, "current_user"),
            (request_reset_account, "current_user"),
            (verify_reset_code, "current_user"),
        ):
            dependency = inspect.signature(route).parameters[
                parameter
            ].default.dependency
            self.assertIs(dependency, require_main_user)

    def test_delete_requires_exact_confirmation_phrase(self):
        with self.assertRaises(ValidationError):
            DeleteAccountRequest(password="secret", confirmation="supprimer")

    def test_wrong_delete_password_does_not_report_expired_session(self):
        request = DeleteAccountRequest(
            password="incorrect",
            confirmation="SUPPRIMER MON COMPTE",
        )
        owner = SimpleNamespace(password_hash="hash")

        with patch("app.routes.auth.verify_password", return_value=False):
            with self.assertRaises(HTTPException) as caught:
                delete_own_account(request, current_user=owner, db=_FakeDb())

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(caught.exception.detail, "Mot de passe incorrect")

    def test_email_failure_rolls_back_reset_code(self):
        db = _FakeDb()
        owner = SimpleNamespace(
            id=8,
            email="owner@example.com",
            interface_language="fr",
        )

        with patch("app.routes.reset.secrets.randbelow", return_value=234567), \
                patch("app.routes.reset.MessageSchema", return_value=object()), \
                patch("app.routes.reset.FastMail") as fast_mail:
            fast_mail.return_value.send_message = AsyncMock(
                side_effect=RuntimeError("SMTP indisponible")
            )
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(request_reset_account(db=db, current_user=owner))

        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(db.flushes, 1)
        self.assertEqual(db.commits, 0)
        self.assertEqual(db.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
