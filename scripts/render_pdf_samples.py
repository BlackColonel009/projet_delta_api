from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.routes.export_financier import (
    _build_complete_report,
    _build_expense_report,
    _build_purchase_report,
    _build_sales_report,
    _build_stock_report,
)
from app.utils.color_theme import build_document_palette


OUTPUT = ROOT / "output" / "pdf"
OUTPUT.mkdir(parents=True, exist_ok=True)


def ns(**values):
    return SimpleNamespace(**values)


def write_html_pdf(template_dir, template_name, context, filename):
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html = env.get_template(template_name).render(**context)
    target = OUTPUT / filename
    with target.open("wb") as stream:
        result = pisa.CreatePDF(html, dest=stream)
    if result.err:
        raise RuntimeError(f"Échec de génération de {filename}")


def render_advertisement():
    static_url = "http://127.0.0.1:8001/static"
    write_html_pdf(
        ROOT / "app" / "repo_scheduler",
        "template_product_mail.html",
        {
            "produit": {
                "nom": "Terminal professionnel Nova X",
                "caracteristiques": (
                    "Écran haute définition, autonomie longue durée, connectivité "
                    "rapide et conception renforcée pour un usage professionnel."
                ),
                "image": f"{static_url}/produits/1752225640.087043.jpg",
            },
            "societe": {
                "nom": "Trade Care Distribution",
                "adresse": "Boulevard du 13 Janvier, Lomé",
                "telephone": "+228 90 00 00 00",
                "email": "contact@trade-care.com",
            },
            "logo_url": f"{static_url}/fac_icon/acc.png",
            "icons": {
                "location": f"{static_url}/fac_icon/loc.png",
                "account": f"{static_url}/fac_icon/acc.png",
                "phone": f"{static_url}/fac_icon/tel.png",
                "mail": f"{static_url}/fac_icon/mail.png",
            },
            "theme": build_document_palette("#7A2CBF"),
        },
        "publicite_produit_exemple.pdf",
    )


def render_invoice():
    client = ns(
        nom="Entreprise Horizon SARL",
        adresse="Quartier Administratif, Lomé",
        telephone="+228 91 11 11 11",
        email="achats@horizon.example",
    )
    lines = []
    for index, (name, quantity, unit_price) in enumerate(
        [
            ("Terminal Nova X", 2, 185000),
            ("Installation et configuration", 1, 45000),
            ("Contrat de maintenance", 1, 75000),
        ],
        start=1,
    ):
        product = ns(
            caracteristiques={"Référence": f"TC-{index:03d}", "Garantie": "12 mois"}
        )
        lines.append(
            ns(
                description=name,
                produit=product,
                unites=[ns(tracabilite=f"SN-2026-{index:04d}")],
                quantite=quantity,
                prix_unitaire=unit_price,
                total_ligne=quantity * unit_price,
            )
        )
    total_ht = sum(line.total_ligne for line in lines)
    invoice = ns(
        id=20260817,
        type=ns(value="facture"),
        date_creation=datetime(2026, 8, 17),
        client=client,
        lignes=lines,
        total_ht=total_ht,
        tva=18,
        total_ttc=total_ht * 1.18,
    )
    write_html_pdf(
        ROOT / "app" / "template",
        "facture_template.html",
        {
            "facture": invoice,
            "societe": {
                "nom": "Trade Care Distribution",
                "adresse": "Boulevard du 13 Janvier, Lomé",
                "nif": "TG-2026-00125",
                "tva": 18,
                "telephone": "+228 90 00 00 00",
                "email": "contact@trade-care.com",
            },
            "logo_url": "http://127.0.0.1:8001/static/fac_icon/acc.png",
            "devise": "FCFA",
            "montant_en_lettres": "Cinq cent soixante-dix-huit mille deux cents francs CFA",
            "color_background": "#F7EFFB",
            "color_text": "#7A2CBF",
            "color_dark": "#572087",
            "color_highlight": "#F0E2FA",
            "color_on_primary": "#FFFFFF",
        },
        "facture_exemple.pdf",
    )


def sample_records():
    sales = []
    purchases = []
    expenses = []
    for index in range(1, 13):
        date = datetime(2026, 8, 18) - timedelta(days=index)
        product = ns(nom=f"Produit professionnel {index}")
        sales.append(
            ns(
                id=1000 + index,
                client=ns(nom=f"Client Entreprise {index}"),
                total_ttc=125000 + index * 9500,
                date_commande=date,
                statut="validée" if index % 3 else "en_attente",
                lignes=[ns(produit=product, quantite=index % 4 + 1)],
            )
        )
        purchases.append(
            ns(
                id=2000 + index,
                fournisseur=ns(nom=f"Fournisseur {index}"),
                total_ttc=80000 + index * 6500,
                date_commande=date,
            )
        )
        expenses.append(
            ns(
                id=3000 + index,
                libelle=f"Dépense opérationnelle {index}",
                montant=12000 + index * 1250,
                categorie="Logistique" if index % 2 else "Fonctionnement",
                date_depense=date,
            )
        )
    return sales, purchases, expenses


def write_report(filename, builder, *args):
    target = OUTPUT / filename
    with target.open("wb") as stream:
        builder(stream, *args)


def render_reports():
    sales, purchases, expenses = sample_records()
    total_sales = sum(item.total_ttc for item in sales)
    total_purchases = sum(item.total_ttc for item in purchases)
    total_expenses = sum(item.montant for item in expenses)
    write_report(
        "rapport_complet_exemple.pdf",
        _build_complete_report,
        "FCFA",
        total_sales,
        total_purchases,
        total_expenses,
        total_sales - total_purchases - total_expenses,
        sales,
        purchases,
        expenses,
        datetime(2026, 8, 17),
    )
    write_report("rapport_depenses_exemple.pdf", _build_expense_report, "FCFA", expenses)
    write_report("rapport_ventes_exemple.pdf", _build_sales_report, "FCFA", sales)
    write_report("rapport_achats_exemple.pdf", _build_purchase_report, "FCFA", purchases)
    stock_rows = [
        {
            "id": index,
            "name": f"Produit de démonstration {index}",
            "characteristics": "Modèle professionnel, garantie 12 mois",
            "traceability": [f"SN-2026-{index:04d}", f"LOT-{index:03d}"],
            "initial": 12 + index,
            "available": 0 if index in (4, 9) else 7 + index,
            "price": 25000 + index * 3750,
        }
        for index in range(1, 16)
    ]
    write_report("etat_stock_exemple.pdf", _build_stock_report, "FCFA", stock_rows)


if __name__ == "__main__":
    render_advertisement()
    render_invoice()
    render_reports()
    print(f"7 PDF générés dans {OUTPUT}")
