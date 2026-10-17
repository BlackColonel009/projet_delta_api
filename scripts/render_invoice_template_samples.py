"""Generate local visual-QA samples for every registered invoice template."""

import shutil
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.model_facture import TypeFacture
from app.services.generate_facture_from_commande import generate_facture_pdf
from app.services.invoice_template_registry import PROFESSIONAL_TEMPLATES
from app.services.simple_invoice_renderer import render_simple_invoice


OUTPUT_DIR = Path(__file__).resolve().parents[2] / "tmp" / "pdfs"


def sample(template_code: str, professional: bool):
    owner = SimpleNamespace(
        societe_ou_entreprise="Trade Care - Boutique Centrale",
        email="direction@example.com",
        username="Direction Delta",
        addresse="Boulevard du 13 Janvier, Lome, Togo",
        nif="TG-2026-0042",
        telephone="+228 90 00 00 00",
        logo_entreprise=None,
        devise="XOF",
        interface_language="fr",
        facture_color="#0F766E",
        tva=18,
    )
    client = SimpleNamespace(
        nom="Savane Miel Cooperative et Partenaires",
        adresse="Rue du Commerce, Kara",
        telephone="+228 91 11 22 33",
        email="comptabilite@example.com",
    )
    descriptions = [
        "Ordinateur portable professionnel avec station d'accueil et garantie etendue",
        "Installation, configuration reseau et transfert securise des donnees",
        "Formation des equipes et accompagnement operationnel",
        "Licence annuelle de gestion et assistance prioritaire",
    ]
    lines = [
        SimpleNamespace(
            produit=None,
            description=descriptions[index % len(descriptions)],
            quantite=(index % 4) + 1,
            prix_unitaire=18500.0 + (index * 1275),
            total_ligne=((index % 4) + 1) * (18500.0 + (index * 1275)),
        )
        for index in range(34 if not professional else 18)
    ]
    total_ht = sum(line.total_ligne for line in lines)
    return SimpleNamespace(
        id=20261017,
        type=TypeFacture.vente,
        date_creation=datetime(2026, 10, 17, 9, 45),
        user=owner,
        sub_user=None,
        client=client,
        fournisseur=None,
        commande_id=None,
        commande_achat_id=None,
        lignes=lines,
        paiements=[SimpleNamespace(montant=total_ht * 0.35)],
        total_ht=total_ht,
        total_ttc=total_ht * 1.18,
        tva=18.0,
        invoice_color_snapshot="#0F766E",
        simple_template_snapshot=template_code if not professional else "simple_classic",
        professional_template_snapshot=(
            template_code if professional else "professional_signature"
        ),
        issuer_name_snapshot="Afi Mensah",
        issuer_role_snapshot="Commerciale",
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for code in ("simple_classic", "simple_compact", "simple_receipt"):
        rendered = render_simple_invoice(sample(code, False), None, sample(code, False).user)
        (OUTPUT_DIR / f"{code}.pdf").write_bytes(rendered.getvalue())

    for definition in PROFESSIONAL_TEMPLATES:
        invoice = sample(definition.code, True)
        generated = generate_facture_pdf(invoice, None)
        destination = OUTPUT_DIR / f"{definition.code}.pdf"
        shutil.move(generated, destination)

    print(f"Generated 11 samples in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
