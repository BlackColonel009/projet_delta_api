import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.schemas.commande_schema import CommandeAchatCreate
from app.services.traceability_service import create_generated_unit


class _FakeDb:
    def __init__(self, next_ids):
        self.next_ids = iter(next_ids)
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        value = self.added[-1]
        if value.id is None:
            value.id = next(self.next_ids)


class TraceabilityGenerationTests(unittest.TestCase):
    @patch(
        "app.services.traceability_service.UniteProduit",
        side_effect=lambda **values: SimpleNamespace(id=None, **values),
    )
    def test_database_id_prevents_reuse_after_permanent_deletion(self, _unit):
        db = _FakeDb([113, 124])

        first = create_generated_unit(
            db,
            produit_id=56,
            suffix="Wisdom",
            commande_achat_id=8,
        )
        # Même si l'unité 113 est supprimée définitivement, la séquence SQL
        # continue et ne recrée jamais sa traçabilité.
        second = create_generated_unit(
            db,
            produit_id=56,
            suffix="Wisdom",
            commande_achat_id=9,
        )

        self.assertEqual(first.tracabilite, "TRAC-56-00000113-Wisdom")
        self.assertEqual(second.tracabilite, "TRAC-56-00000124-Wisdom")
        self.assertNotEqual(first.tracabilite, second.tracabilite)
        self.assertEqual(first.commande_achat_id, 8)

    def test_purchase_rejects_zero_or_negative_quantity(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                CommandeAchatCreate.model_validate({
                    "fournisseur_id": 3,
                    "tva_appliquee": False,
                    "statut": "en_attente",
                    "lignes": [{
                        "produit_id": 56,
                        "quantite": quantity,
                        "prix_unitaire": 100,
                    }],
                })

    def test_purchase_rejects_empty_lines(self):
        with self.assertRaises(ValidationError):
            CommandeAchatCreate.model_validate({
                "fournisseur_id": 3,
                "tva_appliquee": False,
                "statut": "en_attente",
                "lignes": [],
            })


if __name__ == "__main__":
    unittest.main()
