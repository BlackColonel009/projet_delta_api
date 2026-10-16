import unittest

from pydantic import ValidationError

from app.services.depot_pricing_service import (
    MODE_DUREE,
    calculate_deposit_line,
    normalize_pricing_mode,
)
from app.schemas.depot_schema import DepotCreate
from app.schemas.depot_service_schema import DepotServiceCreate
from app.schemas.depot_tarif_schema import DepotTarifCreate


class DepotPricingServiceTests(unittest.TestCase):
    def test_normalizes_legacy_minute_mode(self):
        self.assertEqual(normalize_pricing_mode("minute"), MODE_DUREE)
        self.assertEqual(normalize_pricing_mode("Durée"), MODE_DUREE)

    def test_unit_price_is_multiplied_by_quantity(self):
        result = calculate_deposit_line(
            mode="unitaire",
            quantity=3,
            unit_price=2500,
            price_per_minute=None,
        )
        self.assertEqual(result.total, 7500)
        self.assertIsNone(result.duration_minutes)

    def test_duration_price_is_zero_before_collection(self):
        result = calculate_deposit_line(
            mode="duree",
            quantity=2,
            unit_price=None,
            price_per_minute=50,
        )
        self.assertEqual(result.total, 0)

    def test_duration_price_uses_snapshot_rate_quantity_and_minutes(self):
        result = calculate_deposit_line(
            mode="minute",
            quantity=2,
            unit_price=None,
            price_per_minute=25,
            duration_minutes=90,
        )
        self.assertEqual(result.total, 4500)

    def test_custom_price_remains_fixed_for_duration_service(self):
        result = calculate_deposit_line(
            mode="duree",
            quantity=2,
            unit_price=None,
            price_per_minute=25,
            custom_price=3000,
            duration_minutes=90,
        )
        self.assertEqual(result.total, 6000)

    def test_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            calculate_deposit_line(
                mode="semaine",
                quantity=1,
                unit_price=10,
                price_per_minute=None,
            )

    def test_api_schemas_normalize_and_validate_pricing(self):
        service = DepotServiceCreate(
            nom="Garde minute",
            description=None,
            mode_tarification="minute",
        )
        self.assertEqual(service.mode_tarification, "duree")

        with self.assertRaises(ValidationError):
            DepotTarifCreate(
                service_id=1,
                nom_tarif="Durée standard",
                mode_tarification="duree",
                tarif_par_minute=None,
            )

        with self.assertRaises(ValidationError):
            DepotCreate(
                client_id=1,
                service_id=1,
                description_bien="Sac",
                tarif_items=[],
            )
        with self.assertRaises(ValueError):
            calculate_deposit_line(
                mode="unitaire",
                quantity=0,
                unit_price=10,
                price_per_minute=None,
            )


if __name__ == "__main__":
    unittest.main()
