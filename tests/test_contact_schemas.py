import unittest

from pydantic import ValidationError

from app.schemas.client_schema import ClientCreate, ClientOut
from app.schemas.fournisseur_schema import FournisseurCreate, FournisseurOut


class ContactSchemaTests(unittest.TestCase):
    def test_client_can_be_created_without_email(self):
        client = ClientCreate(
            nom="  Client Test  ",
            telephone="  +22890000000  ",
            email="   ",
        )
        self.assertEqual(client.nom, "Client Test")
        self.assertEqual(client.telephone, "+22890000000")
        self.assertIsNone(client.email)

    def test_supplier_can_be_created_without_email(self):
        supplier = FournisseurCreate(
            nom="Fournisseur Test",
            telephone="+22891000000",
            email=None,
        )
        self.assertIsNone(supplier.email)

    def test_name_and_phone_are_required_for_new_contacts(self):
        with self.assertRaises(ValidationError):
            ClientCreate(nom=" ", telephone="+22890000000")
        with self.assertRaises(ValidationError):
            FournisseurCreate(nom="Fournisseur", telephone=" ")

    def test_invalid_non_empty_email_is_rejected(self):
        with self.assertRaises(ValidationError):
            ClientCreate(
                nom="Client",
                telephone="+22890000000",
                email="adresse-invalide",
            )

    def test_legacy_outputs_still_accept_missing_phone(self):
        client = ClientOut(id=1, nom="Ancien client", telephone=None)
        supplier = FournisseurOut(
            id=1,
            nom="Ancien fournisseur",
            telephone=None,
            date_creation="2026-10-22T10:00:00",
        )
        self.assertIsNone(client.telephone)
        self.assertIsNone(supplier.telephone)


if __name__ == "__main__":
    unittest.main()
