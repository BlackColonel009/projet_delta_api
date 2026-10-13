import inspect
import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.config import settings
from app.routes.auth import update_session_lock
from app.schemas.user_schema import SessionLockUpdate, SessionUnlockRequest
from app.utils.security import create_access_token, get_active_user
from jose import jwt


class SessionLockTests(unittest.TestCase):
    def test_access_token_is_valid_for_twenty_four_hours(self):
        token = create_access_token({"sub": "test@example.com"})
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        expiration = datetime.utcfromtimestamp(payload["exp"])
        remaining = expiration - datetime.utcnow()

        self.assertGreater(remaining, timedelta(hours=23, minutes=59))
        self.assertLessEqual(remaining, timedelta(hours=24))

    def test_only_supported_lock_delays_are_accepted(self):
        for minutes in (0, 5, 15, 30, 60):
            self.assertEqual(
                SessionLockUpdate(session_lock_minutes=minutes).session_lock_minutes,
                minutes,
            )

        with self.assertRaises(ValidationError):
            SessionLockUpdate(session_lock_minutes=10)

        with self.assertRaises(ValidationError):
            SessionLockUpdate(session_lock_minutes=5, password="1234")

        self.assertEqual(
            SessionUnlockRequest(password="A1@bc").password,
            "A1@bc",
        )

    def test_session_lock_endpoint_accepts_main_and_sub_users(self):
        dependency = inspect.signature(update_session_lock).parameters[
            "current_user"
        ].default.dependency

        self.assertIs(dependency, get_active_user)


if __name__ == "__main__":
    unittest.main()
