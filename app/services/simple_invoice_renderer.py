"""Multipage renderer for the three lightweight invoice layouts."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.model_unite_produit import UniteProduit
from app.utils.i18n import language_of, translated


def _color(value: str | None) -> colors.Color:
    try:
        return colors.HexColor(value or "#5C6BC0")
    except (TypeError, ValueError):
        return colors.HexColor("#5C6BC0")


def _document_title(facture, tr) -> str:
    invoice_type = getattr(facture.type, "value", facture.type)
    if invoice_type == "devis":
        return tr("DEVIS", "QUOTE")
    if invoice_type == "proforma":
        return tr("FACTURE PRO FORMA", "PRO FORMA INVOICE")
    return tr("FACTURE", "INVOICE")


def _line_details(db, facture, line, tr) -> str:
    product = line.produit
    details: list[str] = []
    characteristics = getattr(product, "caracteristiques", None) if product else None
    if isinstance(characteristics, dict):
        details.append(", ".join(f"{key}: {value}" for key, value in characteristics.items()))
    elif characteristics:
        details.append(str(characteristics))

    if product and facture.commande_id:
        units = db.query(UniteProduit).filter(
            UniteProduit.produit_id == product.id,
            UniteProduit.commande_vente_id == facture.commande_id,
        ).all()
        codes = ", ".join(unit.tracabilite for unit in units if unit.tracabilite)
        if codes:
            details.append(f"{tr('Codes', 'Codes')}: {codes[:220]}")
    return "<br/>".join(details)


def render_simple_invoice(facture, db, actor) -> BytesIO:
    language = language_of(actor)
    tr = lambda fr, en: translated(language, fr, en)
    code = facture.simple_template_snapshot or "simple_classic"
    if code not in {"simple_classic", "simple_compact", "simple_receipt"}:
        code = "simple_classic"

    accent = _color(facture.invoice_color_snapshot)
    page_size = landscape(A4) if code == "simple_compact" else A4
    compact = code == "simple_compact"
    receipt = code == "simple_receipt"
    horizontal_margin = 28 * mm if receipt else (12 * mm if compact else 17 * mm)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=horizontal_margin,
        rightMargin=horizontal_margin,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"{_document_title(facture, tr)} #{facture.id}",
    )

    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "InvoiceBody",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=7.5 if compact else 8.5,
        leading=9.5 if compact else 11,
        textColor=colors.HexColor("#34313A"),
    )
    small = ParagraphStyle(
        "InvoiceSmall",
        parent=body,
        fontSize=6.8 if compact else 7.5,
        leading=8.2 if compact else 9.2,
        textColor=colors.HexColor("#66616B"),
    )
    heading = ParagraphStyle(
        "InvoiceHeading",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18 if receipt else (20 if compact else 24),
        leading=23,
        textColor=accent,
        alignment=TA_CENTER if receipt else TA_LEFT,
        spaceAfter=3 * mm,
    )
    right = ParagraphStyle("InvoiceRight", parent=body, alignment=TA_RIGHT)
    center = ParagraphStyle("InvoiceCenter", parent=body, alignment=TA_CENTER)
    story = []

    company_name = facture.user.societe_ou_entreprise or facture.user.email
    meta = (
        f"<b>{tr('Date', 'Date')}:</b> {facture.date_creation.strftime('%d/%m/%Y')}<br/>"
        f"<b>N°:</b> {facture.id}"
    )
    company = (
        f"<b>{company_name}</b><br/>"
        f"{facture.user.addresse or ''}<br/>"
        f"NIF: {facture.user.nif or '-'} · {facture.user.telephone or ''}"
    )

    if receipt:
        story.extend([
            Paragraph(company, center),
            Spacer(1, 4 * mm),
            Paragraph(_document_title(facture, tr), heading),
            Paragraph(meta, center),
        ])
    elif compact:
        header = Table(
            [[Paragraph(_document_title(facture, tr), heading), Paragraph(company, right), Paragraph(meta, right)]],
            colWidths=[document.width * 0.38, document.width * 0.37, document.width * 0.25],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -1), 3, accent),
        ]))
        story.append(header)
    else:
        header = Table(
            [[Paragraph(_document_title(facture, tr), heading), Paragraph(company, right)],
             [Paragraph(meta, body), ""]],
            colWidths=[document.width * 0.52, document.width * 0.48],
        )
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBEFORE", (1, 0), (1, -1), 4, accent),
            ("LEFTPADDING", (1, 0), (1, -1), 10),
        ]))
        story.append(header)

    story.append(Spacer(1, 6 * mm))
    recipient = facture.client or facture.fournisseur
    recipient_label = (
        tr("Facturé à", "Bill to") if facture.client else tr("Fournisseur", "Supplier")
    )
    recipient_text = (
        f"<b>{recipient_label}</b><br/>"
        f"{getattr(recipient, 'nom', '')}<br/>"
        f"{getattr(recipient, 'adresse', '') or ''} · {getattr(recipient, 'telephone', '') or ''}"
    )
    recipient_table = Table([[Paragraph(recipient_text, body)]], colWidths=[document.width])
    recipient_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.Color(accent.red, accent.green, accent.blue, alpha=0.08)),
        ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDD8E1")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([recipient_table, Spacer(1, 6 * mm)])

    currency = facture.user.devise or "XOF"
    rows = [[
        Paragraph(f"<b>{tr('Description', 'Description')}</b>", body),
        Paragraph(f"<b>{tr('Qté', 'Qty')}</b>", center),
        Paragraph(f"<b>{tr('PU', 'Unit price')}</b>", right),
        Paragraph("<b>Total</b>", right),
    ]]
    for line in facture.lignes:
        product_name = getattr(line.produit, "nom", None) or line.description
        details = _line_details(db, facture, line, tr)
        description = f"<b>{product_name}</b>"
        if details:
            description += f"<br/><font color='#6D6872' size='7'>{details}</font>"
        rows.append([
            Paragraph(description, body),
            Paragraph(str(line.quantite), center),
            Paragraph(f"{line.prix_unitaire:,.2f} {currency}", right),
            Paragraph(f"{line.total_ligne:,.2f} {currency}", right),
        ])

    widths = [document.width * 0.55, document.width * 0.09, document.width * 0.18, document.width * 0.18]
    items = LongTable(rows, colWidths=widths, repeatRows=1, splitByRow=True)
    grid_color = colors.HexColor("#CFC9D2")
    item_style = [
        ("BACKGROUND", (0, 0), (-1, 0), accent if not receipt else colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white if not receipt else accent),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5 if receipt else 0.5, accent),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4 if compact else 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact else 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, grid_color),
    ]
    if code == "simple_classic":
        item_style.extend([
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F7FA")]),
            ("BOX", (0, 0), (-1, -1), 0.5, grid_color),
        ])
    elif compact:
        item_style.extend([
            ("GRID", (0, 0), (-1, -1), 0.35, grid_color),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    items.setStyle(TableStyle(item_style))
    story.extend([items, Spacer(1, 6 * mm)])

    total_paid = sum(payment.montant for payment in facture.paiements or [])
    balance = max(float(facture.total_ttc or 0) - float(total_paid or 0), 0)
    totals = Table([
        [tr("Total HT", "Subtotal"), f"{facture.total_ht:,.2f} {currency}"],
        [f"{tr('TVA', 'VAT')} ({facture.tva:.0f}%)", f"{facture.total_ttc - facture.total_ht:,.2f} {currency}"],
        [tr("Total TTC", "Total incl. tax"), f"{facture.total_ttc:,.2f} {currency}"],
        [tr("Reste à payer", "Balance due"), f"{balance:,.2f} {currency}"],
    ], colWidths=[document.width * 0.6, document.width * 0.4])
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -2), (-1, -2), accent),
        ("TEXTCOLOR", (0, -2), (-1, -2), colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, grid_color),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, grid_color),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(totals)

    issuer = facture.issuer_name_snapshot or facture.user.username or facture.user.email
    issuer_role = facture.issuer_role_snapshot or tr("Propriétaire", "Owner")
    status = tr("PAYÉE", "PAID") if balance <= 0 else tr("NON SOLDÉE", "OUTSTANDING")
    story.extend([
        Spacer(1, 7 * mm),
        Paragraph(f"<b>{status}</b>", ParagraphStyle(
            "InvoiceStatus", parent=heading, fontSize=12, alignment=TA_RIGHT,
        )),
        Paragraph(
            f"<b>{tr('Émise par', 'Issued by')}:</b> {issuer} · {issuer_role}",
            small,
        ),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#77727B"))
        canvas.drawString(doc.leftMargin, 6.5 * mm, company_name)
        canvas.drawRightString(
            page_size[0] - doc.rightMargin,
            6.5 * mm,
            f"{tr('Page', 'Page')} {doc.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer
