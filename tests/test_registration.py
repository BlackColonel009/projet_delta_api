import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routes.auth import register_user
from app.schemas.user_schema import UserCreate


class _Query:
    def __init__(self, db):
        self.db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.db.saved_user


class _Db:
    def __init__(self):
        self.saved_user = None

    def query(self, _model):
        return _Query(self)

    def add(self, user):
        self.saved_user = user
        user.id = 41

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, _user):
        pass


class RegistrationTests(unittest.TestCase):
    @patch("app.routes.auth.create_free_subscription")
    @patch("app.routes.auth.create_access_token", return_value="token")
    @patch("app.routes.auth.hash_password", return_value="hashed")
    @patch("time.sleep")
    def test_simple_registration_defaults_to_main_free_french(
        self, _sleep, _hash, _token, create_subscription
    ):
        db = _Db()
        payload = UserCreate(
            email="owner@example.com",
            password="secret123",
            societe_ou_entreprise="Example SARL",
        )

        with patch(
            "app.routes.auth.User",
            side_effect=lambda **values: SimpleNamespace(**values),
        ):
            response = register_user(payload, db)

        self.assertEqual(response["access_token"], "token")
        self.assertTrue(db.saved_user.is_main_user)
        self.assertEqual(db.saved_user.account_type, "bronze_free")
        self.assertEqual(db.saved_user.interface_language, "fr")
        create_subscription.assert_called_once_with(db, user_id=41)

    @patch("app.routes.auth.create_free_subscription")
    @patch("app.routes.auth.create_access_token", return_value="token")
    @patch("app.routes.auth.hash_password", return_value="hashed")
    @patch("time.sleep")
    def test_legacy_main_user_flag_cannot_create_orphan_account(
        self, _sleep, _hash, _token, create_subscription
    ):
        db = _Db()
        payload = UserCreate(
            email="english@example.com",
            password="secret123",
            is_main_user=False,
            account_type="paid",
            interface_language="en",
        )

        with patch(
            "app.routes.auth.User",
            side_effect=lambda **values: SimpleNamespace(**values),
        ):
            register_user(payload, db)

        self.assertTrue(db.saved_user.is_main_user)
        self.assertEqual(db.saved_user.account_type, "bronze_free")
        self.assertEqual(db.saved_user.interface_language, "en")
        create_subscription.assert_called_once_with(db, user_id=41)


if __name__ == "__main__":
    unittest.main()
