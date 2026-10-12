import unittest

from app.routes.facture import _can_delete_unit_after_purchase_cancellation


class PurchaseCancellationTests(unittest.TestCase):
    def test_only_available_and_unavailable_units_can_be_deleted(self):
        self.assertTrue(
            _can_delete_unit_after_purchase_cancellation("disponible")
        )
        self.assertTrue(
            _can_delete_unit_after_purchase_cancellation("Indisponible")
        )
        self.assertFalse(_can_delete_unit_after_purchase_cancellation("vendu"))
        self.assertFalse(
            _can_delete_unit_after_purchase_cancellation("en cours")
        )
        self.assertFalse(_can_delete_unit_after_purchase_cancellation(None))


if __name__ == "__main__":
    unittest.main()
