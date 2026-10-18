import unittest

from pydantic import ValidationError

from app.schemas.enterprise_schema import EnterpriseCreate
from app.services.business_type_registry import (
    BUSINESS_TYPE_REGISTRY,
    CREATABLE_BUSINESS_TYPES,
    business_type_catalog,
    service_for_business_type,
)


class BusinessTypeFoundationTests(unittest.TestCase):
    def test_catalog_codes_and_services_are_unique(self):
        services = [item["service_code"] for item in BUSINESS_TYPE_REGISTRY.values()]
        self.assertEqual(len(services), len(set(services)))
        self.assertEqual(len(business_type_catalog()), 5)

    def test_legacy_consignment_cannot_be_created(self):
        self.assertNotIn("legacy_consignment", CREATABLE_BUSINESS_TYPES)

    def test_every_new_business_type_maps_to_its_own_service(self):
        self.assertEqual(service_for_business_type("commerce"), "gestion_principale")
        self.assertEqual(service_for_business_type("laundry"), "laundry")
        self.assertEqual(service_for_business_type("vehicle_rental"), "vehicle_rental")
        self.assertEqual(service_for_business_type("property_rental"), "property_rental")

    def test_creation_schema_accepts_the_four_public_types(self):
        for code in sorted(CREATABLE_BUSINESS_TYPES):
            payload = EnterpriseCreate(name="Entreprise pilote", business_type=code)
            self.assertEqual(payload.business_type, code)

    def test_creation_schema_rejects_legacy_type(self):
        with self.assertRaises(ValidationError):
            EnterpriseCreate(
                name="Ancienne consigne",
                business_type="legacy_consignment",
            )


if __name__ == "__main__":
    unittest.main()
