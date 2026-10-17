import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.utils.subscription_guard import (
    SubscriptionAccess,
    enforce_quota_limit,
    subscription_is_expired,
)


def _access(**overrides):
    values = {
        "owner_id": 7,
        "plan_code": "bronze_classic",
        "plan_name": "Bronze Classic",
        "features": frozenset({"reports", "full_qr"}),
        "max_sub_users": 2,
        "max_enterprises": 1,
        "max_products": 1000,
        "max_clients": 1000,
        "max_invoices_per_month": 200,
    }
    values.update(overrides)
    return SubscriptionAccess(**values)


class SubscriptionAccessTests(unittest.TestCase):
    def test_feature_is_read_from_company_plan(self):
        access = _access()

        self.assertTrue(access.has_feature("reports"))
        self.assertFalse(access.has_feature("multi_depot"))

    def test_advanced_feature_includes_its_basic_capability(self):
        access = _access(features=frozenset({"custom_theme", "full_qr"}))

        self.assertTrue(access.has_feature("theme_colors"))
        self.assertTrue(access.has_feature("basic_qr"))

    def test_quota_allows_usage_below_limit(self):
        enforce_quota_limit(_access(), "max_sub_users", 1, "sous-utilisateurs")

    def test_quota_returns_a_stable_structured_error(self):
        with self.assertRaises(HTTPException) as caught:
            enforce_quota_limit(
                _access(),
                "max_sub_users",
                2,
                "sous-utilisateurs",
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(caught.exception.detail["code"], "QUOTA_REACHED")
        self.assertEqual(caught.exception.detail["limit"], 2)
        self.assertEqual(caught.exception.detail["current"], 2)

    def test_enterprise_quota_counts_the_primary_enterprise(self):
        with self.assertRaises(HTTPException) as caught:
            enforce_quota_limit(
                _access(max_enterprises=1),
                "max_enterprises",
                1,
                "entreprises et annexes",
            )

        self.assertEqual(caught.exception.detail["resource"], "max_enterprises")

    def test_null_quota_and_superadmin_are_unlimited(self):
        enforce_quota_limit(
            _access(max_products=None),
            "max_products",
            1_000_000,
            "produits",
        )
        superadmin = _access(unlimited=True, features=frozenset())
        self.assertTrue(superadmin.has_feature("any_future_feature"))

    def test_free_plan_does_not_expire(self):
        past = datetime.utcnow() - timedelta(days=365)

        self.assertFalse(subscription_is_expired("bronze_free", past))
        self.assertTrue(subscription_is_expired("gold", past))


if __name__ == "__main__":
    unittest.main()
