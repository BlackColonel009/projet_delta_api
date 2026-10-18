import unittest
from datetime import datetime, timedelta
from pydantic import ValidationError
from app.routes.property_rental import BLOCKING_STATUSES, _add_month
from app.schemas.property_rental_schema import OccupancyCreate, PropertyPaymentCreate
from app.services.property_reminder_service import _key
from types import SimpleNamespace


class PropertyRentalFoundationTests(unittest.TestCase):
    def test_short_stay_requires_end(self):
        with self.assertRaises(ValidationError): OccupancyCreate(unit_id=1, client_id=1, occupancy_type="stay", start_at=datetime.now())
    def test_invalid_period_is_rejected(self):
        now=datetime.now()
        with self.assertRaises(ValidationError): OccupancyCreate(unit_id=1, client_id=1, occupancy_type="lease", start_at=now, end_at=now-timedelta(days=1))
    def test_monthly_schedule_handles_short_month(self):
        self.assertEqual(_add_month(datetime(2026,1,31),1,28).day,28)
    def test_active_occupancies_block_overlap(self):
        self.assertEqual(BLOCKING_STATUSES,{"reserved","active","late"})
    def test_zero_payment_is_rejected(self):
        with self.assertRaises(ValidationError): PropertyPaymentCreate(kind="rent", amount=0, due_id=1)
    def test_reminder_key_is_stable_inside_frequency_bucket(self):
        now=datetime(2026,10,18,8)
        due=SimpleNamespace(due_date=datetime(2026,10,13,8))
        self.assertEqual(_key(due,now,3),("overdue:1","overdue"))


if __name__ == "__main__": unittest.main()
