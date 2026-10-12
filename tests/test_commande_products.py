import unittest
from datetime import datetime
from types import SimpleNamespace

from app.routes.commande import (
    _serialize_commande_achat,
    _serialize_commande_vente,
    _serialize_ligne_commande,
)
from app.schemas.commande_schema import CommandeAchatOut, CommandeVenteOut


def _line(*, product_name="Clavier", description="Ancien clavier"):
    return SimpleNamespace(
        id=3,
        produit_id=12,
        produit=(
            SimpleNamespace(nom=product_name) if product_name is not None else None
        ),
        description=description,
        quantite=2,
        prix_unitaire=15000.0,
        total_ligne=30000.0,
    )


class CommandeProductSerializationTests(unittest.TestCase):
    def test_line_includes_product_name(self):
        result = _serialize_ligne_commande(_line())
        self.assertEqual(result["nom_produit"], "Clavier")

    def test_deleted_product_keeps_historical_description(self):
        result = _serialize_ligne_commande(
            _line(product_name=None, description="Clavier mécanique")
        )
        self.assertEqual(result["nom_produit"], "Clavier mécanique")

    def test_sale_response_contains_lines(self):
        order = SimpleNamespace(
            id=1,
            client_id=5,
            date_commande=datetime(2026, 10, 12, 10),
            total_ht=30000.0,
            total_ttc=35400.0,
            tva=5400.0,
            tva_appliquee=True,
            statut="en_attente",
            lignes=[_line()],
        )
        response = CommandeVenteOut.model_validate(_serialize_commande_vente(order))
        self.assertEqual(response.lignes[0].nom_produit, "Clavier")

    def test_purchase_response_contains_lines(self):
        order = SimpleNamespace(
            id=2,
            fournisseur_id=8,
            date_commande=datetime(2026, 10, 12, 11),
            total_ht=30000.0,
            total_ttc=30000.0,
            tva=0.0,
            tva_appliquee=False,
            statut="en_attente",
            lignes=[_line()],
        )
        response = CommandeAchatOut.model_validate(_serialize_commande_achat(order))
        self.assertEqual(response.lignes[0].quantite, 2)


if __name__ == "__main__":
    unittest.main()
