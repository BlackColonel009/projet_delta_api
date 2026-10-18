import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.routes.laundry import TRANSITIONS
from app.schemas.laundry_schema import (
    LaundryItemCreate,
    LaundryOrderCreate,
    LaundryPaymentCreate,
)


class LaundryFoundationTests(unittest.TestCase):
    def test_happy_path_reaches_delivery(self):
        path = [
            "received",
            "sorted",
            "processing",
            "drying",
            "ironing",
            "ready",
            "delivered",
        ]
        for current, target in zip(path, path[1:]):
            self.assertIn(target, TRANSITIONS[current])

    def test_terminal_states_cannot_be_reopened(self):
        self.assertEqual(TRANSITIONS["delivered"], set())
        self.assertEqual(TRANSITIONS["cancelled"], set())

    def test_incident_can_resume_or_cancel(self):
        self.assertEqual(
            TRANSITIONS["incident"],
            {"processing", "ready", "cancelled"},
        )

    def test_order_requires_at_least_one_item(self):
        with self.assertRaises(ValidationError):
            LaundryOrderCreate(client_id=1, items=[])

    def test_item_quantity_and_price_are_validated(self):
        with self.assertRaises(ValidationError):
            LaundryItemCreate(service_id=1, category="Chemise", quantity=0)
        with self.assertRaises(ValidationError):
            LaundryItemCreate(
                service_id=1,
                category="Chemise",
                unit_price=-1,
            )

    def test_express_order_accepts_a_due_date(self):
        due_at = datetime.utcnow() + timedelta(hours=3)
        order = LaundryOrderCreate(
            client_id=1,
            priority="express",
            due_at=due_at,
            items=[LaundryItemCreate(service_id=1, category="Chemise")],
        )
        self.assertEqual(order.priority, "express")
        self.assertEqual(order.due_at, due_at)

    def test_payment_must_be_positive(self):
        with self.assertRaises(ValidationError):
            LaundryPaymentCreate(amount=0)


if __name__ == "__main__":
    unittest.main()
