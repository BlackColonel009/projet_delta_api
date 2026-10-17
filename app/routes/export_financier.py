import datetime
from collections import defaultdict
from html import escape
from io import BytesIO
from textwrap import wrap

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    LongTable,
    TableStyle,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services.report_design import ReportDesign, company_owner, money
from app.database import get_db
from app.models.model_commande import CommandeAchat, CommandeVente
from app.models.model_depense import Depense
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.schemas.user_schema import RoleEnum
from app.utils.permissions import check_role
from app.services.enterprise_service import actor_enterprise_id

router = APIRouter(prefix="/export", tags=["Exports Financiers"])

PRIMARY = colors.HexColor("#7A2CBF")
PRIMARY_DARK = colors.HexColor("#54206F")
PRIMARY_SOFT = colors.HexColor("#F0E2FA")
INK = colors.HexColor("#241A29")
MUTED = colors.HexColor("#6C6072")
BORDER = colors.HexColor("#E4DCE8")
ROW_ALT = colors.HexColor("#FAF8FB")
DANGER_SOFT = colors.HexColor("#FFE4E6")
DANGER = colors.HexColor("#A72836")


class BrandedReportDocument(SimpleDocTemplate):
    def build(self, story, **kwargs):
        title = getattr(story[0], 'getPlainText', lambda: 'Rapport financier')()
        if 'Global' in title or not title:
            title = 'Rapport financier global'
        # Replace the legacy global cover and fixed page references.
        if isinstance(story[0], Spacer):
            title = 'Rapport financier global'
            first_break = next((i for i, item in enumerate(story) if isinstance(item, PageBreak)), -1)
            if first_break >= 0:
                story = story[first_break + 1:]
        story = self.design.cover(title, 'Situation à la date de génération') + story
        for item in story:
            if isinstance(item, Table):
                item.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), self.design.dark)]))
                # Retain explicit stock warning rows while replacing neutral stripes.
                for command in tuple(item._bkgrndcmds):
                    if command[0] == 'BACKGROUND' and command[3] == ROW_ALT:
                        item.setStyle(TableStyle([('BACKGROUND', command[1], command[2], self.design.soft)]))
                for column, header in enumerate(item._cellvalues[0]):
                    if 'Montant' in str(header) or 'Total' in str(header) or 'Prix' in str(header):
                        for row in item._cellvalues[1:]:
                            cell = row[column]
                            if isinstance(cell, Paragraph):
                                cell.style = ParagraphStyle('Amount', parent=cell.style, alignment=2)
        self.title = title + ' - ' + self.design.name
        self.author = self.design.name
        return super().build(story, **kwargs)


def _styles(company=None):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TradeCareReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=PRIMARY_DARK,
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareCoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=PRIMARY_DARK,
            alignment=TA_LEFT,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            alignment=TA_JUSTIFY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareSummaryLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareSummaryValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=PRIMARY_DARK,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TradeCareCenter",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            alignment=TA_CENTER,
        )
    )
    design = ReportDesign(company)
    for name in ("TradeCareReportTitle", "TradeCareCoverTitle", "TradeCareSummaryValue"):
        styles[name].textColor = design.dark
    return styles


def _document(buffer, *, landscape_mode=False, company=None):
    doc = BrandedReportDocument(
        buffer,
        pagesize=landscape(A4) if landscape_mode else A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.65 * cm,
        bottomMargin=1.8 * cm,
        title="Trade Care",
        author="Trade Care",
    )
    doc.design = ReportDesign(company)
    return doc


def _decorate_page(pdf, doc):
    doc.design.decorate(pdf, doc)


def _title_block(title, styles):
    return [
        Paragraph(escape(title), styles["TradeCareReportTitle"]),
        HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=14),
    ]


def _p(value, style):
    return Paragraph(escape(str(value if value is not None else "")), style)


def _activity_analysis(company, records, devise, *, expenses=False):
    design = ReportDesign(company)
    monthly = defaultdict(float)
    groups = defaultdict(float)
    for record in records:
        date = record.date_depense if expenses else record.date_commande
        amount = float((record.montant if expenses else record.total_ttc) or 0)
        monthly[date.strftime('%Y-%m')] += amount
        if expenses:
            label = record.categorie or 'Non classée'
        else:
            party = getattr(record, 'client', None) or getattr(record, 'fournisseur', None)
            label = getattr(party, 'nom', 'Inconnu')
        groups[label] += amount
    total = sum(monthly.values())
    story = [design.p('Analyse de la période', 'Heading2'),
             design.p(f'{len(records)} opérations enregistrées, pour un total de {money(total, devise)}. '
                      'Le périmètre correspond aux opérations détaillées dans ce rapport.')]
    # Limit charts to legible windows; tables retain all records.
    months = sorted(monthly)[-12:]
    story += design.section('Activité mensuelle (12 derniers mois actifs)',
                            design.chart('Montants par mois', months, [[monthly[m] for m in months]], ['Montant'], devise),
                            'Les mois affichés correspondent aux mois comportant des opérations. Le détail conserve toutes les opérations du périmètre.')
    ranked = sorted(groups.items(), key=lambda item: item[1], reverse=True)[:6]
    story += design.section('Répartition (6 premiers postes)',
                            design.chart('Principaux postes', [f'P{i+1}' for i in range(len(ranked))],
                                         [[v for _, v in ranked]], ['Montant'], devise),
                            '; '.join(f'P{i+1} : {name} ({money(value, devise)})' for i, (name, value) in enumerate(ranked)) or 'Aucune opération enregistrée.')
    return story + [PageBreak(), design.p('Détail des opérations', 'Heading1')]


def _content_chunks(values, *, max_lines=10, line_width=28):
    """Découpe une cellule volumineuse en fragments tenant sur une page PDF."""
    lines = []
    for value in values:
        text = str(value if value is not None else "").strip()
        wrapped = wrap(
            text or "-",
            width=line_width,
            break_long_words=True,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or ["-"])

    return [
        lines[index:index + max_lines]
        for index in range(0, len(lines), max_lines)
    ] or [["-"]]


def _styled_table(
    data,
    col_widths,
    *,
    alignments=None,
    danger_rows=None,
    use_long_table=False,
):
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("LEADING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.45, BORDER),
    ]

    for row in range(2, len(data), 2):
        style_commands.append(("BACKGROUND", (0, row), (-1, row), ROW_ALT))

    for column, alignment in (alignments or {}).items():
        style_commands.append(("ALIGN", (column, 1), (column, -1), alignment))

    for row in danger_rows or []:
        style_commands.extend(
            [
                ("BACKGROUND", (0, row), (-1, row), DANGER_SOFT),
                ("TEXTCOLOR", (0, row), (-1, row), DANGER),
            ]
        )

    table_class = LongTable if use_long_table else Table
    table = table_class(
        data,
        colWidths=col_widths,
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
    )
    table.setStyle(TableStyle(style_commands))
    return table


def _build_complete_report(
    buffer,
    devise,
    total_ventes,
    total_achats,
    total_depenses,
    benefice_net,
    ventes,
    achats,
    depenses,
    generated_at,
    company=None,
):
    styles = _styles(company)
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    story = [
        Spacer(1, 1.3 * cm),
        Paragraph("Rapport Financier Global", styles["TradeCareCoverTitle"]),
        HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=24),
        Paragraph("Sommaire", styles["TradeCareSummaryLabel"]),
        Spacer(1, 10),
        Paragraph("- Résumé Financier : Page 2", styles["TradeCareBody"]),
        Spacer(1, 7),
        Paragraph("- Ventes : Page 3", styles["TradeCareBody"]),
        Spacer(1, 7),
        Paragraph("- Achats : Page 4", styles["TradeCareBody"]),
        Spacer(1, 7),
        Paragraph("- Dépenses : Page 5", styles["TradeCareBody"]),
        Spacer(1, 1.5 * cm),
        Paragraph(
            f"Date : {generated_at.strftime('%d/%m/%Y')}",
            styles["TradeCareSmall"],
        ),
        PageBreak(),
        *_title_block("Résumé Financier", styles),
    ]

    summary_data = [
        ["Indicateur", "Montant"],
        [_p("Total Ventes", styles["TradeCareSummaryLabel"]), _p(f"{total_ventes:.2f} {devise}", styles["TradeCareSummaryValue"])],
        [_p("Total Achats", styles["TradeCareSummaryLabel"]), _p(f"{total_achats:.2f} {devise}", styles["TradeCareSummaryValue"])],
        [_p("Total Dépenses", styles["TradeCareSummaryLabel"]), _p(f"{total_depenses:.2f} {devise}", styles["TradeCareSummaryValue"])],
        [_p("Résultat simplifié", styles["TradeCareSummaryLabel"]), _p(f"{benefice_net:.2f} {devise}", styles["TradeCareSummaryValue"])],
    ]
    story.append(_styled_table(summary_data, [8.3 * cm, 8.3 * cm], alignments={1: "RIGHT"}))
    design = ReportDesign(company)
    story.extend([Spacer(1, 14), design.p('Le résultat présenté est le solde TTC ventes - achats - dépenses. Il ne constitue pas un bénéfice comptable ni une trésorerie disponible.'),
                  design.chart('Comparaison des montants enregistrés', ['Ventes', 'Achats', 'Dépenses'],
                               [[float(total_ventes), float(total_achats), float(total_depenses)]], ['Montant'], devise)])

    sales_data = [["Vente ID", "Client", f"Total ({devise})", "Date"]]
    for sale in ventes:
        client_name = sale.client.nom if sale.client else "Inconnu"
        sales_data.append(
            [
                _p(sale.id, center),
                _p(client_name, body),
                _p(f"{sale.total_ttc:.2f}", body),
                _p(sale.date_commande.strftime("%d/%m/%Y"), center),
            ]
        )
    story.extend([PageBreak(), *_title_block("Détail des Ventes", styles)])
    story.extend(_activity_analysis(company, ventes, devise))
    story.append(_styled_table(sales_data, [2.2 * cm, 7.0 * cm, 4.0 * cm, 3.4 * cm], alignments={0: "CENTER", 2: "RIGHT", 3: "CENTER"}))

    purchase_data = [["Achat ID", "Fournisseur", f"Total ({devise})", "Date"]]
    for purchase in achats:
        supplier_name = purchase.fournisseur.nom if purchase.fournisseur else "Inconnu"
        purchase_data.append(
            [
                _p(purchase.id, center),
                _p(supplier_name, body),
                _p(f"{purchase.total_ttc:.2f}", body),
                _p(purchase.date_commande.strftime("%d/%m/%Y"), center),
            ]
        )
    story.extend([PageBreak(), *_title_block("Détail des Achats", styles)])
    story.extend(_activity_analysis(company, achats, devise))
    story.append(_styled_table(purchase_data, [2.2 * cm, 7.0 * cm, 4.0 * cm, 3.4 * cm], alignments={0: "CENTER", 2: "RIGHT", 3: "CENTER"}))

    expense_data = [["Dépense ID", "Libellé", f"Montant ({devise})", "Catégorie", "Date"]]
    for expense in depenses:
        expense_data.append(
            [
                _p(expense.id, center),
                _p(expense.libelle, body),
                _p(f"{expense.montant:.2f}", body),
                _p(expense.categorie, body),
                _p(expense.date_depense.strftime("%d/%m/%Y"), center),
            ]
        )
    story.extend([PageBreak(), *_title_block("Détail des Dépenses", styles)])
    story.extend(_activity_analysis(company, depenses, devise, expenses=True))
    story.append(_styled_table(expense_data, [2.1 * cm, 5.0 * cm, 3.2 * cm, 3.5 * cm, 2.8 * cm], alignments={0: "CENTER", 2: "RIGHT", 4: "CENTER"}))

    _document(buffer, company=company).build(
        story,
        onFirstPage=_decorate_page,
        onLaterPages=_decorate_page,
    )


def _build_expense_report(buffer, devise, depenses, company=None):
    styles = _styles(company)
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    data = [["Dépense ID", "Libellé", f"Montant ({devise})", "Catégorie", "Date"]]
    for expense in depenses:
        data.append(
            [
                _p(expense.id, center),
                _p(expense.libelle, body),
                _p(f"{expense.montant:.2f}", body),
                _p(expense.categorie, body),
                _p(expense.date_depense.strftime("%d/%m/%Y"), center),
            ]
        )
    story = [*_title_block("Rapport des Dépenses", styles)]
    story.extend(_activity_analysis(company, depenses, devise, expenses=True))
    story.append(_styled_table(data, [2.1 * cm, 5.0 * cm, 3.2 * cm, 3.5 * cm, 2.8 * cm], alignments={0: "CENTER", 2: "RIGHT", 4: "CENTER"}))
    _document(buffer, company=company).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_sales_report(buffer, devise, ventes, company=None):
    styles = _styles(company)
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    data = [["Vente ID", "Client", "Produits", f"Total ({devise})", "Date", "Statut"]]
    for sale in ventes:
        client_name = sale.client.nom if sale.client else "Inconnu"
        products = [
            f"{line.produit.nom if line.produit else 'Produit inconnu'} x{line.quantite}"
            for line in sale.lignes
        ]
        data.append(
            [
                _p(sale.id, center),
                _p(client_name, body),
                Paragraph("<br/>".join(escape(item) for item in products), body),
                _p(f"{sale.total_ttc:.2f}", body),
                _p(sale.date_commande.strftime("%d/%m/%Y"), center),
                _p(sale.statut, center),
            ]
        )
    story = [*_title_block("Rapport des Ventes", styles)]
    story.extend(_activity_analysis(company, ventes, devise))
    story.append(_styled_table(data, [1.7 * cm, 2.8 * cm, 5.1 * cm, 2.5 * cm, 2.6 * cm, 2.2 * cm], alignments={0: "CENTER", 3: "RIGHT", 4: "CENTER", 5: "CENTER"}))
    _document(buffer, company=company).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_purchase_report(buffer, devise, achats, company=None):
    styles = _styles(company)
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    data = [["Achat ID", "Fournisseur", f"Total ({devise})", "Date"]]
    for purchase in achats:
        supplier_name = purchase.fournisseur.nom if purchase.fournisseur else "Inconnu"
        data.append(
            [
                _p(purchase.id, center),
                _p(supplier_name, body),
                _p(f"{purchase.total_ttc:.2f}", body),
                _p(purchase.date_commande.strftime("%d/%m/%Y"), center),
            ]
        )
    story = [*_title_block("Rapport des Achats", styles)]
    story.extend(_activity_analysis(company, achats, devise))
    story.append(_styled_table(data, [2.2 * cm, 7.0 * cm, 4.0 * cm, 3.4 * cm], alignments={0: "CENTER", 2: "RIGHT", 3: "CENTER"}))
    _document(buffer, company=company).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_stock_report(buffer, devise, rows, company=None):
    styles = _styles(company)
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    data = [["ID", "Nom du produit", "Caractéristiques", "Codes / Traçabilités", "Stock initial", "Disponible", f"Prix ({devise})"]]
    danger_rows = []
    for row in rows:
        name_chunks = _content_chunks([row["name"]])
        characteristic_chunks = _content_chunks([row["characteristics"]])
        traceability_chunks = _content_chunks(row["traceability"])
        chunk_count = max(
            len(name_chunks),
            len(characteristic_chunks),
            len(traceability_chunks),
        )

        for chunk_index in range(chunk_count):
            first_chunk = chunk_index == 0
            characteristics = (
                characteristic_chunks[chunk_index]
                if chunk_index < len(characteristic_chunks)
                else []
            )
            traceability = (
                traceability_chunks[chunk_index]
                if chunk_index < len(traceability_chunks)
                else []
            )
            names = (
                name_chunks[chunk_index]
                if chunk_index < len(name_chunks)
                else []
            )
            raw_price = row.get("price")
            price = f"{float(raw_price or 0):.2f}" if first_chunk else ""
            data.append(
                [
                    _p(row["id"] if first_chunk else "", center),
                    Paragraph(
                        "<br/>".join(escape(line) for line in names),
                        body,
                    ),
                    Paragraph(
                        "<br/>".join(escape(line) for line in characteristics),
                        body,
                    ),
                    Paragraph(
                        "<br/>".join(escape(line) for line in traceability),
                        body,
                    ),
                    _p(row["initial"] if first_chunk else "", center),
                    _p(row["available"] if first_chunk else "", center),
                    _p(price, body),
                ]
            )
            if row["available"] == 0:
                danger_rows.append(len(data) - 1)
    story = [*_title_block("État du Stock", styles)]
    design = ReportDesign(company)
    ranked = sorted(rows, key=lambda row: row['available'], reverse=True)[:8]
    story.extend(design.section('Disponibilité actuelle',
                 design.chart('Produits les plus disponibles', [f'P{i+1}' for i in range(len(ranked))],
                              [[float(row['available']) for row in ranked]], ['Unités']),
                 f"{sum(row['available'] == 0 for row in rows)} produits sans disponibilité. " +
                 '; '.join(f"P{i+1} : {row['name']}" for i, row in enumerate(ranked))))
    story.append(PageBreak())
    story.append(design.p('Inventaire détaillé', 'Heading1'))
    story.append(
        _styled_table(
            data,
            [1.3 * cm, 4.6 * cm, 5.1 * cm, 5.3 * cm, 2.7 * cm, 2.7 * cm, 3.2 * cm],
            alignments={0: "CENTER", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT"},
            danger_rows=danger_rows,
            use_long_table=True,
        )
    )
    _document(buffer, landscape_mode=True, company=company).build(
        story,
        onFirstPage=_decorate_page,
        onLaterPages=_decorate_page,
    )


def _response(buffer, filename):
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.get("/rapport-complet")
def export_rapport_complet(
    db: Session = Depends(get_db),
    current_user=Depends(
        check_role([RoleEnum.admin, RoleEnum.caissier, RoleEnum.comptable])
    ),
):
    parent_user_id = actor_enterprise_id(current_user)
    company = company_owner(db, current_user)
    devise = company.devise or "FCFA"
    total_ventes = (
        db.query(func.sum(CommandeVente.total_ttc))
        .filter(CommandeVente.enterprise_id == parent_user_id)
        .scalar()
        or 0
    )
    total_achats = (
        db.query(func.sum(CommandeAchat.total_ttc))
        .filter(CommandeAchat.enterprise_id == parent_user_id)
        .scalar()
        or 0
    )
    total_depenses = (
        db.query(func.sum(Depense.montant))
        .filter(Depense.enterprise_id == parent_user_id)
        .scalar()
        or 0
    )
    ventes = (
        db.query(CommandeVente)
        .filter(CommandeVente.enterprise_id == parent_user_id)
        .order_by(CommandeVente.date_commande.desc())
        .all()
    )
    achats = (
        db.query(CommandeAchat)
        .filter(CommandeAchat.enterprise_id == parent_user_id)
        .order_by(CommandeAchat.date_commande.desc())
        .all()
    )
    depenses = (
        db.query(Depense)
        .filter(Depense.enterprise_id == parent_user_id)
        .order_by(Depense.date_depense.desc())
        .all()
    )
    buffer = BytesIO()
    _build_complete_report(
        buffer,
        devise,
        total_ventes,
        total_achats,
        total_depenses,
        total_ventes - total_achats - total_depenses,
        ventes,
        achats,
        depenses,
        datetime.datetime.now(),
        company=company,
    )
    filename = f"rapport-financier-{datetime.datetime.now().strftime('%d-%m-%Y')}.pdf"
    return _response(buffer, filename)


@router.get("/rapport-depenses")
def export_rapport_depenses(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = actor_enterprise_id(current_user)
    company = company_owner(db, current_user)
    devise = company.devise or "FCFA"
    depenses = db.query(Depense).filter(Depense.enterprise_id == parent_user_id).order_by(Depense.date_depense.desc()).all()
    buffer = BytesIO()
    _build_expense_report(buffer, devise, depenses, company=company)
    return _response(buffer, "rapport_depenses.pdf")


@router.get("/rapport-ventes")
def export_rapport_ventes(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = actor_enterprise_id(current_user)
    company = company_owner(db, current_user)
    devise = company.devise or "FCFA"
    ventes = (
        db.query(CommandeVente)
        .filter(CommandeVente.enterprise_id == parent_user_id)
        .filter(CommandeVente.statut.in_(["validée", "en_attente"]))
        .order_by(CommandeVente.date_commande.desc())
        .all()
    )
    buffer = BytesIO()
    _build_sales_report(buffer, devise, ventes, company=company)
    return _response(buffer, "rapport_ventes.pdf")


@router.get("/rapport-achats")
def export_rapport_achats(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = actor_enterprise_id(current_user)
    company = company_owner(db, current_user)
    devise = company.devise or "FCFA"
    achats = db.query(CommandeAchat).filter(CommandeAchat.enterprise_id == parent_user_id).order_by(CommandeAchat.date_commande.desc()).all()
    buffer = BytesIO()
    _build_purchase_report(buffer, devise, achats, company=company)
    return _response(buffer, "rapport_achats.pdf")


@router.get("/etat-stock")
def export_etat_stock(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = actor_enterprise_id(current_user)
    parent_user = getattr(current_user, "parent_user", None)
    company = company_owner(db, current_user)
    devise = company.devise or "FCFA"
    produits = (
        db.query(Produit)
        .filter(Produit.enterprise_id == parent_user_id, Produit.date_suppression.is_(None))
        .order_by(Produit.nom.asc())
        .all()
    )

    initial_stock_by_product = defaultdict(int)
    available_stock_by_product = defaultdict(int)
    traceability_by_product = defaultdict(list)
    unit_rows = (
        db.query(
            UniteProduit.produit_id,
            UniteProduit.tracabilite,
            UniteProduit.statut,
        )
        .join(Produit, UniteProduit.produit_id == Produit.id)
        .filter(
            Produit.enterprise_id == parent_user_id,
            UniteProduit.enterprise_id == parent_user_id,
            Produit.date_suppression.is_(None),
        )
        .all()
    )
    for product_id, traceability, status in unit_rows:
        initial_stock_by_product[product_id] += 1
        if str(status or "").strip().lower() == "disponible":
            available_stock_by_product[product_id] += 1
        if traceability:
            traceability_by_product[product_id].append(traceability)

    rows = []
    for product in produits:
        tracked_units = initial_stock_by_product[product.id]
        declared_stock = max(int(product.quantite or 0), 0)
        rows.append(
            {
                "id": product.id,
                "name": product.nom,
                "characteristics": product.caracteristiques or "-",
                "traceability": sorted(set(traceability_by_product.get(product.id, []))) or ["-"],
                "initial": tracked_units or declared_stock,
                "available": (
                    available_stock_by_product[product.id]
                    if tracked_units
                    else declared_stock
                ),
                "price": product.prix_vente or 0,
            }
        )

    buffer = BytesIO()
    _build_stock_report(buffer, devise, rows, company=company)
    return _response(buffer, "etat_stock.pdf")
