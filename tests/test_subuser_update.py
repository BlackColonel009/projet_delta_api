import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes.auth import update_subuser


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args):
        return self

    def first(self):
        return self._result


class _FakeDb:
    def __init__(self, sub_user, duplicate=None):
        self._results = [sub_user, duplicate]
        self.commits = 0
        self.refreshes = 0

    def query(self, _model):
        return _FakeQuery(self._results.pop(0) if self._results else None)

    def commit(self):
        self.commits += 1

    def refresh(self, _instance):
        self.refreshes += 1


def _sub_user():
    return SimpleNamespace(
        id=7,
        username="ancien",
        password_hash="ancien_hash",
        role="Technicien(ne)",
        avatar_url="/avatar.png",
        bio="Bio",
        telephone="+22890000000",
        created_at=None,
    )


class UpdateSubUserTests(unittest.TestCase):
    @patch("app.routes.auth.attach_subuser_to_enterprise")
    @patch("app.routes.auth.log_action")
    @patch("app.routes.auth.hash_password", return_value="nouveau_hash")
    def test_updates_every_field_and_hashes_new_password(
        self,
        hash_password,
        _log_action,
        attach_subuser,
    ):
        sub_user = _sub_user()
        db = _FakeDb(sub_user, duplicate=None)
        db._results.append(SimpleNamespace(name="Comptable"))

        response = update_subuser(
            sub_id=7,
            username="  nouveau  ",
            password="motdepasse",
            role="Comptable",
            avatar_url=None,
            bio="  Nouvelle bio  ",
            telephone=" +22891111111 ",
            enterprise_id=None,
            db=db,
            current_user=SimpleNamespace(id=3),
        )

        self.assertEqual(sub_user.username, "nouveau")
        self.assertEqual(sub_user.password_hash, "nouveau_hash")
        self.assertEqual(sub_user.role, "Comptable")
        self.assertEqual(sub_user.bio, "Nouvelle bio")
        self.assertEqual(sub_user.telephone, "+22891111111")
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.refreshes, 1)
        self.assertEqual(response["sub_user"]["username"], "nouveau")
        hash_password.assert_called_once_with("motdepasse")
        attach_subuser.assert_called_once_with(db, sub_user, None)

    @patch("app.routes.auth.attach_subuser_to_enterprise")
    @patch("app.routes.auth.log_action")
    @patch("app.routes.auth.hash_password")
    def test_keeps_password_when_no_new_password_is_sent(
        self,
        hash_password,
        _log_action,
        attach_subuser,
    ):
        sub_user = _sub_user()
        db = _FakeDb(sub_user)
        db._results.append(SimpleNamespace(name="Technicien(ne)"))

        update_subuser(
            sub_id=7,
            username="ancien",
            password=None,
            role="Technicien(ne)",
            avatar_url=None,
            bio="",
            telephone="",
            enterprise_id=None,
            db=db,
            current_user=SimpleNamespace(id=3),
        )

        self.assertEqual(sub_user.password_hash, "ancien_hash")
        self.assertIsNone(sub_user.bio)
        self.assertIsNone(sub_user.telephone)
        hash_password.assert_not_called()
        attach_subuser.assert_called_once_with(db, sub_user, None)

    @patch("app.routes.auth.log_action")
    def test_rejects_a_password_shorter_than_eight_characters(
        self,
        _log_action,
    ):
        sub_user = _sub_user()
        db = _FakeDb(sub_user)

        with self.assertRaises(HTTPException) as raised:
            update_subuser(
                sub_id=7,
                username=None,
                password="court",
                role=None,
                avatar_url=None,
                bio=None,
                telephone=None,
                enterprise_id=None,
                db=db,
                current_user=SimpleNamespace(id=3),
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(db.commits, 0)


if __name__ == "__main__":
    unittest.main()
