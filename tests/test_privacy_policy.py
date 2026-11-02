import unittest

from pydantic import ValidationError

from app.schemas.user_schema import UserCreate
from app.services.privacy_policy_service import (
    PRIVACY_POLICY_VERSION,
    public_privacy_policy_metadata,
)


class PrivacyPolicyTests(unittest.TestCase):
    def _payload(self, **overrides):
        values = {
            "email": "owner@example.com",
            "password": "secret123",
            "societe_ou_entreprise": "Example SARL",
            "privacy_policy_accepted": True,
            "privacy_policy_version": PRIVACY_POLICY_VERSION,
        }
        values.update(overrides)
        return values

    def test_current_policy_is_required(self):
        payload = UserCreate(**self._payload())
        self.assertTrue(payload.privacy_policy_accepted)
        self.assertEqual(payload.privacy_policy_version, PRIVACY_POLICY_VERSION)

    def test_refusal_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(**self._payload(privacy_policy_accepted=False))

    def test_obsolete_version_is_rejected(self):
        with self.assertRaises(ValidationError):
            UserCreate(**self._payload(privacy_policy_version="2025-05-20"))

    def test_public_metadata_exposes_current_version(self):
        metadata = public_privacy_policy_metadata()
        self.assertEqual(metadata["version"], PRIVACY_POLICY_VERSION)
        self.assertTrue(metadata["public_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
