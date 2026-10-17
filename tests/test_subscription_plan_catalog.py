import inspect
import unittest

from pydantic import ValidationError

from app.routes.subscription_plan import update_subscription_plan
from app.schemas.subscription_schema import GrantSubscriptionRequest
from app.schemas.subscription_plan_schema import SubscriptionPlanUpdate
from app.services.subscription_service import (
    legacy_subscription_type,
    subscription_duration_days,
)
from app.utils.security import require_super_user


def _valid_payload(**overrides):
    values = {
        "name": "Or",
        "description": "Offre recommandée",
        "monthly_price": 12500,
        "annual_price": 125000,
        "currency": "xof",
        "max_sub_users": 8,
        "max_enterprises": 3,
        "max_products": 10000,
        "max_clients": None,
        "max_invoices_per_month": None,
        "features": ["annual_comparison", "client_followup"],
        "is_active": True,
        "is_featured": True,
        "sort_order": 30,
    }
    values.update(overrides)
    return values


class SubscriptionPlanCatalogTests(unittest.TestCase):
    def test_plan_values_are_validated_and_normalized(self):
        plan = SubscriptionPlanUpdate(**_valid_payload())

        self.assertEqual(plan.currency, "XOF")
        self.assertEqual(len(plan.features), 2)
        self.assertIsNone(plan.max_clients)
        self.assertEqual(plan.max_enterprises, 3)

    def test_multi_enterprise_features_are_valid_catalog_values(self):
        plan = SubscriptionPlanUpdate(
            **_valid_payload(
                features=[
                    "multi_enterprise",
                    "group_dashboard",
                    "global_stock_search",
                ]
            )
        )

        self.assertEqual(len(plan.features), 3)

    def test_unknown_feature_is_rejected(self):
        with self.assertRaises(ValidationError):
            SubscriptionPlanUpdate(**_valid_payload(features=["unknown_feature"]))

    def test_negative_price_is_rejected(self):
        with self.assertRaises(ValidationError):
            SubscriptionPlanUpdate(**_valid_payload(monthly_price=-1))

    def test_plan_update_route_requires_superadmin(self):
        dependency = inspect.signature(update_subscription_plan).parameters[
            "_"
        ].default.dependency

        self.assertIs(dependency, require_super_user)

    def test_new_grant_payload_resolves_annual_cycle(self):
        payload = GrantSubscriptionRequest(
            plan_code="gold",
            billing_cycle="annual",
        )

        self.assertEqual(payload.resolved_cycle.value, "annual")
        self.assertEqual(subscription_duration_days("annual"), 365)
        self.assertEqual(legacy_subscription_type("annual"), "yearly")

    def test_legacy_grant_payload_remains_supported(self):
        payload = GrantSubscriptionRequest(type="monthly")

        self.assertEqual(payload.resolved_cycle.value, "monthly")
        self.assertEqual(subscription_duration_days("monthly"), 30)

    def test_grant_payload_requires_a_billing_cycle(self):
        with self.assertRaises(ValidationError):
            GrantSubscriptionRequest(plan_code="gold")


if __name__ == "__main__":
    unittest.main()
