import unittest
from datetime import datetime, timedelta
from pydantic import ValidationError
from app.routes.vehicle_rental import BLOCKING_STATUSES, TRANSITIONS
from app.schemas.vehicle_rental_schema import RentalChargeCreate, RentalPaymentCreate, ReservationCreate


class VehicleRentalFoundationTests(unittest.TestCase):
    def test_end_must_be_after_start(self):
        now = datetime.now()
        with self.assertRaises(ValidationError):
            ReservationCreate(vehicle_id=1, client_id=1, start_at=now, end_at=now - timedelta(hours=1))

    def test_rental_happy_path(self):
        path = ["reserved", "confirmed", "prepared", "rented", "return_expected", "inspection", "completed"]
        for current, target in zip(path, path[1:]):
            self.assertIn(target, TRANSITIONS[current])

    def test_terminal_states_are_closed(self):
        self.assertEqual(TRANSITIONS["completed"], set())
        self.assertEqual(TRANSITIONS["cancelled"], set())

    def test_active_reservations_block_overlap(self):
        self.assertTrue({"reserved", "confirmed", "rented", "late"}.issubset(BLOCKING_STATUSES))

    def test_financial_amounts_are_positive(self):
        with self.assertRaises(ValidationError):
            RentalPaymentCreate(kind="deposit", amount=0)
        with self.assertRaises(ValidationError):
            RentalChargeCreate(kind="damage", label="Rayure", amount=-1)


if __name__ == "__main__":
    unittest.main()
