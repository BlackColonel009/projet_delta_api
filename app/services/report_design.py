"""Shared company branding and paginated, commented financial reports."""
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, unquote

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, LongTable, TableStyle, KeepTogether, HRFlowable
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from app.utils.color_theme import build_document_palette

THEMES = {'tradecare': '#7A2CBF', 'ocean': '#1565C0', 'emerald': '#087F5B',
          'sunset': '#B45309', 'ruby': '#B4233C', 'midnight': '#334C8C'}
MONTHS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']


def company_owner(db, user):
    if getattr(user, 'is_main_user', True):
        return user
    from app.models.model_user import User
    return db.query(User).filter(User.id == user.parent_user_id).first() or user


class ReportDesign:
    def __init__(self, company=None):
        self.company = company
        self.name = getattr(company, 'societe_ou_entreprise', None) or 'Trade Care'
        self.palette = build_document_palette(THEMES.get(getattr(company, 'app_theme', 'tradecare'), THEMES['tradecare']))
        self.primary = colors.HexColor(self.palette['primary'])
        self.dark = colors.HexColor(self.palette['primary_dark'])
        self.soft = colors.HexColor(self.palette['primary_pale'])
        self.styles = getSampleStyleSheet()
        self.styles.add(ParagraphStyle(name='ReportBody', fontName='Helvetica', fontSize=10, leading=15,
                                      alignment=TA_JUSTIFY, spaceAfter=10, textColor=colors.HexColor('#263244')))
        self.styles['Title'].textColor = self.dark
        self.styles['Title'].alignment = 0
        self.styles['Title'].fontSize = 28
        self.styles['Title'].leading = 34
        self.styles['Heading1'].textColor = self.dark
        self.styles['Heading1'].spaceAfter = 14
        self.styles['Heading2'].textColor = self.dark
        self.styles['Heading2'].spaceBefore = 12

    def p(self, text, style='ReportBody'):
        return Paragraph(escape(str(text)), self.styles[style])

    def logo(self):
        # Uploaded logos are served from /static; resolve locally without fetching URLs.
        value = getattr(self.company, 'logo_entreprise', None)
        if not value:
            return []
        url_path = unquote(urlparse(value).path).replace('\\', '/')
        if '/static/' not in url_path:
            return []
        root = Path(__file__).resolve().parents[2] / 'upload'
        path = (root / url_path.split('/static/', 1)[1]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            return []
        try:
            logo = Image(str(path))
            scale = min(120 / logo.imageWidth, 75 / logo.imageHeight)
            logo.drawWidth, logo.drawHeight = logo.imageWidth * scale, logo.imageHeight * scale
            logo.hAlign = 'LEFT'
            return [logo, Spacer(1, 24)]
        except (OSError, ValueError):
            return []

    def cover(self, title, period):
        return [Spacer(1, 32), *self.logo(), self.p(self.name, 'Heading1'), Spacer(1, 24),
                self.p(title, 'Title'), HRFlowable(width='100%', thickness=3, color=self.primary, spaceAfter=14),
                self.p(period, 'Heading2'),
                Spacer(1, 24), self.p('Analyse de l’activité, indicateurs clés et détails de gestion.'),
                self.p(getattr(self.company, 'addresse', None) or ''),
                self.p('Établi le ' + datetime.now(timezone.utc).strftime('%d/%m/%Y')),
                PageBreak()]

    def decorate(self, pdf, doc):
        width, height = doc.pagesize
        pdf.saveState()
        pdf.setFillColor(self.primary)
        pdf.rect(0, height - 9, width, 9, fill=1, stroke=0)
        pdf.setFont('Helvetica', 8)
        pdf.setFillColor(self.dark)
        pdf.drawString(doc.leftMargin, height - 28, self.name[:80])
        pdf.setStrokeColor(self.primary)
        pdf.line(doc.leftMargin, 32, width - doc.rightMargin, 32)
        pdf.setFont('Helvetica-Oblique', 9)
        pdf.drawString(doc.leftMargin, 19, 'tradecare')
        pdf.setFont('Helvetica', 8)
        pdf.drawRightString(width - doc.rightMargin, 19, f'Page {doc.page}')
        pdf.restoreState()

    def table(self, headers, rows, widths=None):
        style = ParagraphStyle('Cell', fontName='Helvetica', fontSize=8, leading=11)
        head = ParagraphStyle('Head', parent=style, fontName='Helvetica-Bold', textColor=colors.white)
        data = [[Paragraph(escape(str(h)), head) for h in headers]]
        data += [[Paragraph(escape(str(v)), style) for v in row] for row in rows]
        if not rows:
            data.append([Paragraph('Aucune donnée', style)] + [''] * (len(headers) - 1))
        table = LongTable(data, colWidths=widths or [483 / len(headers)] * len(headers), repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), self.dark),
                                  ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.soft]),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('TOPPADDING', (0, 0), (-1, -1), 8),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                                  ('LINEBELOW', (0, 0), (-1, -1), .3, colors.HexColor('#DDE2EA'))]))
        return table

    def chart(self, title, labels, series, names, currency=''):
        drawing = Drawing(480, 210)
        drawing.add(String(0, 196, title, fontName='Helvetica-Bold', fontSize=11, fillColor=self.dark))
        if not labels or not any(any(v != 0 for v in values) for values in series):
            drawing.add(String(25, 100, 'Aucune donnée disponible pour ce graphique.', fontSize=10))
            return drawing
        palette = [self.primary, colors.HexColor('#338A9B'), colors.HexColor('#C77C30'), colors.HexColor('#B4233C')]
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 62, 45, 400, 130
        chart.data = series
        chart.categoryAxis.categoryNames = [str(x)[:22] for x in labels]
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.labelTextFormat = lambda v: f'{v:,.0f}'.replace(',', ' ')
        chart.valueAxis.visibleGrid = True
        chart.valueAxis.gridStrokeColor = colors.HexColor('#E3E7ED')
        for i in range(len(series)):
            chart.bars[i].fillColor = palette[i % len(palette)]
        drawing.add(chart)
        for i, name in enumerate(names):
            drawing.add(String(62 + i * 135, 12, name, fontSize=8, fillColor=palette[i % len(palette)]))
        drawing.add(String(0, 178, currency, fontSize=7))
        return drawing

    def distribution(self, labels, values):
        drawing = Drawing(480, 220)
        if not any(v > 0 for v in values):
            drawing.add(String(30, 100, 'Aucune charge positive enregistrée.', fontSize=10))
            return drawing
        chart = Pie()
        chart.x, chart.y, chart.width, chart.height = 75, 25, 170, 170
        chart.data = [max(v, 0) for v in values]
        total = sum(chart.data)
        chart.labels = [f'{v / total * 100:.1f} %' for v in chart.data]
        chart.slices[0].fillColor = self.primary
        chart.slices[1].fillColor = colors.HexColor('#338A9B')
        drawing.add(chart)
        for i, label in enumerate(labels):
            drawing.add(String(310, 150 - i * 30, label, fontSize=10,
                               fillColor=self.primary if i == 0 else colors.HexColor('#338A9B')))
        return drawing

    def section(self, title, chart, comment):
        return [self.p(title, 'Heading2'), KeepTogether([chart, Spacer(1, 8)]), self.p(comment)]

    def build(self, buffer, story, pagesize=A4):
        doc = SimpleDocTemplate(buffer, pagesize=pagesize, leftMargin=56, rightMargin=56,
                                topMargin=48, bottomMargin=48, title='Rapport - ' + self.name, author=self.name)
        doc.build(story, onFirstPage=self.decorate, onLaterPages=self.decorate)
        buffer.seek(0)


def money(value, currency):
    return f'{float(value):,.2f} {currency}'.replace(',', ' ')


def build_annual_report(buffer, company, year, monthly, stock, invoices, new_clients=0):
    design = ReportDesign(company)
    currency = getattr(company, 'devise', None) or 'FCFA'
    series = [[float(monthly[key].get(m, 0) or 0) for m in range(1, 13)] for key in ('ventes', 'achats', 'depenses')]
    sales, purchases, expenses = [sum(s) for s in series]
    net = sales - purchases - expenses
    results = [series[0][i] - series[1][i] - series[2][i] for i in range(12)]
    story = design.cover('Rapport financier annuel', f'Exercice {year} · du 01/01 au 31/12/{year}')
    story += [design.p('Synthèse de l’exercice', 'Heading1'), design.table(['Indicateur', 'Montant'],
              [(name, money(v, currency)) for name, v in [('Ventes validées', sales), ('Achats validés', purchases),
               ('Dépenses', expenses), ('Solde ventes - achats', sales - purchases), ('Résultat simplifié', net)]]), Spacer(1, 16)]
    margin = f'{net / sales * 100:.1f} %' if sales else 'non calculable en l’absence de ventes'
    story += [design.p(f'Le résultat simplifié est de {money(net, currency)}. Le rapport résultat / ventes est {margin}. '
                       'Ce solde est calculé à partir des ventes TTC, achats TTC et dépenses enregistrées ; '
                       'il ne constitue pas un bénéfice comptable ni un solde de trésorerie.'),
              design.p('Parcours du rapport : activité mensuelle, résultat, structure des charges, clients et impayés, stock actuel et détails.'), PageBreak()]
    story += [design.p('Activité et performance', 'Heading1')]
    best = max(range(12), key=lambda i: series[0][i])
    comment = (f'Le mois le plus actif est {MONTHS[best]} avec {money(series[0][best], currency)} de ventes. '
               f'Les achats représentent {purchases / sales * 100:.1f} % des ventes.' if sales else
               'Aucune vente validée n’est enregistrée sur cet exercice. Les charges doivent être examinées indépendamment du chiffre d’affaires.')
    story += design.section('Évolution mensuelle', design.chart('Ventes, achats et dépenses', MONTHS, series, ['Ventes', 'Achats', 'Dépenses'], currency), comment)
    story += design.section('Résultat par mois', design.chart('Solde mensuel simplifié', MONTHS, [results], ['Résultat'], currency),
                            f'{sum(v < 0 for v in results)} mois présentent un solde négatif. Les mois sans opérations apparaissent à zéro.')
    story += [PageBreak(), design.p('Structure des charges', 'Heading1')]
    story += design.section('Comparaison annuelle', design.chart('Répartition des montants', ['Ventes', 'Achats', 'Dépenses'], [[sales, purchases, expenses]], ['Montant'], currency),
                            f'Les décaissements théoriques achats et dépenses totalisent {money(purchases + expenses, currency)}. '
                            'Ces montants décrivent les opérations enregistrées et ne prouvent pas leur règlement.')
    story += design.section('Répartition des charges positives', design.distribution(['Achats', 'Dépenses'], [purchases, expenses]),
                            'Ce diagramme présente la part des achats et des dépenses dans les charges positives enregistrées.')
    story += [PageBreak(), design.p('Tableau mensuel', 'Heading1'), design.p(f'Montants en {currency}.'), design.table(['Mois', 'Ventes', 'Achats', 'Dépenses', 'Résultat'],
              [[MONTHS[i]] + [money(s[i], '') for s in series] + [money(results[i], '')] for i in range(12)]), PageBreak()]
    story += [design.p('Clients et factures non réglées', 'Heading1'), design.p(f'{new_clients} nouveaux clients enregistrés pendant l’exercice.')]
    remaining = lambda f: max(float(f.total_ttc or 0) - sum(float(p.montant or 0) for p in getattr(f, 'paiements', [])), 0)
    groups = [invoices['ventes_non_reglees'], invoices['achats_non_reglees']]
    balances = [sum(remaining(f) for f in group) for group in groups]
    story += design.section('Encours à suivre', design.chart('Restes à régler', ['Clients', 'Fournisseurs'], [balances], ['Encours'], currency),
                            f'Les créances clients restantes s’élèvent à {money(balances[0], currency)} et les dettes fournisseurs à {money(balances[1], currency)}. '
                            'Les paiements partiels enregistrés sont déduits. Les soldes sont ceux observés à la génération, pour les factures émises pendant l’exercice.')
    for title, group, attr in zip(['Factures clients', 'Factures fournisseurs'], groups, ['client', 'fournisseur']):
        story += [design.p(title, 'Heading2'), design.table(['Réf.', 'Tiers', 'Date', 'Reste à payer'],
                  [[f.id, getattr(getattr(f, attr, None), 'nom', 'Inconnu'), f.date_creation.strftime('%d/%m/%Y'), money(remaining(f), currency)] for f in group])]
    story += [PageBreak(), design.p('Stock disponible au moment de l’édition', 'Heading1'),
              design.p('Le stock présenté est le stock actuel des unités suivies. Il ne reconstitue pas un inventaire historique au 31 décembre.')]
    ranked = sorted(stock.items(), key=lambda item: item[1]['stock_disponible'], reverse=True)[:8]
    story += design.section('Disponibilité des produits', design.chart('Produits les plus disponibles (8 maximum)',
              [f'P{i+1}' for i in range(len(ranked))], [[v['stock_disponible'] for _, v in ranked]], ['Unités']),
              ' ; '.join(f'P{i+1} : {name}' for i, (name, _) in enumerate(ranked)) or 'Aucun produit suivi.')
    story += [design.table(['Produit', 'Unités suivies', 'Disponibles'], [[name, v['stock_total'], v['stock_disponible']] for name, v in stock.items()]),
              Spacer(1, 15), design.p('Priorités de suivi', 'Heading2'),
              design.p('Examiner les mois déficitaires, rapprocher les paiements des factures et contrôler les produits sans disponibilité. '
                       'Les graphiques et commentaires utilisent exclusivement les données enregistrées dans Trade Care.')]
    design.build(buffer, story)
