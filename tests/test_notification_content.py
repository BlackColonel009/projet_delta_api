import unittest

from app.schemas.notification_schema import (
    NotificationCreate,
    sanitize_notification_text,
)


class NotificationContentTests(unittest.TestCase):
    def test_image_path_is_removed(self):
        cleaned = sanitize_notification_text(
            "Machine, image_url: /static/products/ordinateur.jpg, ajoutée"
        )
        self.assertNotIn("image_url", cleaned)
        self.assertNotIn("/static", cleaned)

    def test_readable_multiline_notification_is_preserved(self):
        notification = NotificationCreate(
            titre="Nouvelle vente",
            message="Client : Delta\nProduits : 2 × PC\nMontant : 500 000 XOF",
        )
        self.assertIn("Client : Delta", notification.message)
        self.assertIn("2 × PC", notification.message)

    def test_empty_message_is_rejected(self):
        with self.assertRaises(ValueError):
            NotificationCreate(titre="Test", message="   ")


if __name__ == "__main__":
    unittest.main()
