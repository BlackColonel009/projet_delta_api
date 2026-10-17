"""Génère deux factures de consigne fictives pour la recette visuelle."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.routes.facture_depot import _document


def _sample_invoice():
    company = SimpleNamespace(
        societe_ou_entreprise="Trade Care Démonstration",
        facture_color="#0F766E",
        app_theme="emerald",
        devise="FCFA",
        logo_entreprise=None,
        addresse="Lomé, Togo",
        email="contact@tradecare.example",
    )
    client = SimpleNamespace(nom="Entreprise Horizon", email="client@example.com")
    service = SimpleNamespace(nom="Consigne professionnelle")
    tariffs = [
        SimpleNamespace(nom_tarif="Prise en charge", mode_tarification="unitaire"),
        SimpleNamespace(nom_tarif="Garde sécurisée", mode_tarification="duree"),
    ]
    items = [
        SimpleNamespace(
            tarif=tariffs[0],
            description="Contrôle, étiquetage et mise en sécurité",
            quantite=2,
            prix_personnalise=None,
            mode_tarification_snapshot="unitaire",
            prix_unitaire_snapshot=2500,
            montant_total=5000,
        ),
        SimpleNamespace(
            tarif=tariffs[1],
            description="Conservation pendant 180 minutes",
            quantite=1,
            prix_personnalise=None,
            mode_tarification_snapshot="duree",
            prix_unitaire_snapshot=25,
            montant_total=4500,
        ),
    ]
    depot = SimpleNamespace(
        client=client,
        service=service,
        description_bien="Deux ordinateurs portables avec leurs chargeurs",
        date_depot=datetime(2026, 10, 16, 8, 30),
        tarif_items=items,
    )
    return SimpleNamespace(
        id=42,
        depot=depot,
        user=company,
        created_at=datetime(2026, 10, 16, 11, 30),
        date_facture=datetime(2026, 10, 16, 11, 30),
        montant_ht=9500,
        tva=0,
        montant_ttc=9500,
    )


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "output" / "pdf"
    output.mkdir(parents=True, exist_ok=True)
    invoice = _sample_invoice()
    for invoice_format in ("simple", "professional"):
        buffer = _document(
            invoice,
            receipt=False,
            language_user=SimpleNamespace(interface_language="fr"),
            invoice_format=invoice_format,
        )
        (output / f"facture_consigne_{invoice_format}_exemple.pdf").write_bytes(
            buffer.getvalue()
        )


if __name__ == "__main__":
    main()
