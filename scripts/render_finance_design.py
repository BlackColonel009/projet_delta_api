"""Deterministic demo and layout stress checks; no database access."""
from pathlib import Path
from types import SimpleNamespace as NS
from io import BytesIO
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.report_design import build_annual_report, ReportDesign
from pypdf import PdfReader

output = ROOT / 'output/pdf'
output.mkdir(parents=True, exist_ok=True)
company = NS(societe_ou_entreprise='Trade Care Distribution', app_theme='ocean', devise='FCFA',
             addresse='Boulevard du 13 Janvier, Lomé', logo_entreprise='/static/fac_icon/acc.png')
monthly = {'ventes': {i: i * 180000 for i in range(1, 13)},
           'achats': {i: i * 110000 for i in range(1, 13)},
           'depenses': {i: 250000 for i in range(1, 13)}}
stock = {f'Produit professionnel {i}': {'stock_total': i + 10, 'stock_disponible': i} for i in range(15)}
from datetime import datetime
invoice = NS(id=1, total_ttc=350000, date_creation=datetime(2026, 3, 1),
             client=NS(nom='Client Horizon'), fournisseur=None, paiements=[NS(montant=150000)])
invoices = {'ventes_non_reglees': [invoice], 'achats_non_reglees': []}
buffer = BytesIO()
build_annual_report(buffer, company, 2026, monthly, stock, invoices, 8)
target = output / 'rapport_finance_design.pdf'
target.write_bytes(buffer.getvalue())
reader = PdfReader(buffer)
text = '\n'.join(page.extract_text() for page in reader.pages)
assert '200 000.00' in text, 'Partial payments must be deducted'
assert all('tradecare' in page.extract_text() for page in reader.pages)
assert 'stock actuel' in text
print(f'Demo: {len(reader.pages)} pages; footer and partial payments verified.')
empty = BytesIO()
build_annual_report(empty, company, 2026, {key: {} for key in monthly}, {},
                    {'ventes_non_reglees': [], 'achats_non_reglees': []})
assert 'Aucune donnée' in '\n'.join(page.extract_text() for page in PdfReader(empty).pages)
print('Empty data: verified.')
stress = BytesIO()
build_annual_report(stress, company, 2026, monthly,
                    {'Produit avec une description longue ' * 8 + str(i): {'stock_total': 10, 'stock_disponible': 0} for i in range(80)},
                    {'ventes_non_reglees': [invoice] * 80, 'achats_non_reglees': []})
assert len(PdfReader(stress).pages) > len(reader.pages)
print('Long tables: pagination verified.')
