import inspect
import unittest

from pydantic import ValidationError

from app.routes.subscription_request import (
    approve_request,
    create_request,
    list_requests_for_admin,
)
from app.schemas.subscription_request_schema import SubscriptionChangeRequestCreate
from app.utils.security import require_main_user, require_super_user


class SubscriptionRequestTests(unittest.TestCase):
    def test_request_accepts_monthly_and_annual_cycles(self):
        monthly = SubscriptionChangeRequestCreate(
            plan_code="gold",
            billing_cycle="monthly",
        )
        annual = SubscriptionChangeRequestCreate(
            plan_code="diamond_pro",
            billing_cycle="annual",
            note="Nous souhaitons être rappelés.",
        )

        self.assertEqual(monthly.billing_cycle.value, "monthly")
        self.assertEqual(annual.billing_cycle.value, "annual")

    def test_request_rejects_unknown_cycle(self):
        with self.assertRaises(ValidationError):
            SubscriptionChangeRequestCreate(
                plan_code="gold",
                billing_cycle="weekly",
            )

    def test_company_request_requires_main_user(self):
        dependency = inspect.signature(create_request).parameters[
            "current_user"
        ].default.dependency

        self.assertIs(dependency, require_main_user)

    def test_admin_review_routes_require_superadmin(self):
        list_dependency = inspect.signature(list_requests_for_admin).parameters[
            "_"
        ].default.dependency
        approve_dependency = inspect.signature(approve_request).parameters[
            "reviewer"
        ].default.dependency

        self.assertIs(list_dependency, require_super_user)
        self.assertIs(approve_dependency, require_super_user)


if __name__ == "__main__":
    unittest.main()
