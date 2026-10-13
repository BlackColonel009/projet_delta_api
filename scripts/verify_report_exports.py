"""Exercise PDF builders independently of API/database startup configuration."""
import ast
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as NS
import sys
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
source = ast.parse((root / 'app/routes/export_financier.py').read_text(encoding='utf-8'))
nodes = []
for node in source.body:
    if isinstance(node, ast.ImportFrom) and (node.module.startswith(('fastapi', 'sqlalchemy', 'app.database', 'app.models', 'app.schemas', 'app.utils.permissions'))):
        continue
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'router' for t in node.targets):
        continue
    if isinstance(node, ast.FunctionDef) and (node.decorator_list or node.name == '_response'):
        continue
    nodes.append(node)
namespace = {}
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'export_builders', 'exec'), namespace)
company = NS(societe_ou_entreprise='Entreprise Émeraude', app_theme='emerald', logo_entreprise=None)
date = datetime(2026, 4, 12)
sale = NS(id=1, client=NS(nom='Client A'), fournisseur=None, total_ttc=12000,
          date_commande=date, statut='validée', lignes=[NS(produit=NS(nom='Terminal'), quantite=2)])
purchase = NS(id=2, fournisseur=NS(nom='Fournisseur B'), total_ttc=6000, date_commande=date)
expense = NS(id=3, libelle='Transport', montant=2000, categorie='Logistique', date_depense=date)
rows = [dict(id=1, name='Terminal', characteristics='Écran professionnel', traceability=['TC001'], initial=8, available=4, price=6000)]
calls = [('_build_sales_report', ('FCFA', [sale])), ('_build_purchase_report', ('FCFA', [purchase])),
         ('_build_expense_report', ('FCFA', [expense])), ('_build_stock_report', ('FCFA', rows)),
         ('_build_complete_report', ('FCFA', 12000, 6000, 2000, 4000, [sale], [purchase], [expense], date))]
for name, args in calls:
    buffer = BytesIO()
    namespace[name](buffer, *args, company=company)
    reader = PdfReader(buffer)
    assert all('tradecare' in page.extract_text() for page in reader.pages)
    assert 'Entreprise Émeraude' in reader.pages[0].extract_text()
    assert len(reader.pages) >= 3
    temp = root / 'tmp/pdfs'
    temp.mkdir(parents=True, exist_ok=True)
    (temp / (name + '_verification.pdf')).write_bytes(buffer.getvalue())
    print(name, len(reader.pages), 'pages OK')
