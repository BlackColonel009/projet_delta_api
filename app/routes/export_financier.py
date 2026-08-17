import datetime
from collections import defaultdict
from html import escape
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
    TableStyle,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_commande import CommandeAchat, CommandeVente
from app.models.model_depense import Depense
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from app.schemas.user_schema import RoleEnum
from app.utils.permissions import check_role

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


def _styles():
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
            alignment=TA_LEFT,
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
    return styles


def _document(buffer, *, landscape_mode=False):
    return SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if landscape_mode else A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.65 * cm,
        bottomMargin=1.35 * cm,
        title="Trade Care",
        author="Trade Care",
    )


def _decorate_page(pdf, doc):
    width, height = doc.pagesize
    pdf.saveState()
    pdf.setFillColor(PRIMARY)
    pdf.rect(0, height - 8, width, 8, stroke=0, fill=1)
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.5)
    pdf.line(doc.leftMargin, 0.85 * cm, width - doc.rightMargin, 0.85 * cm)
    pdf.restoreState()


def _title_block(title, styles):
    return [
        Paragraph(escape(title), styles["TradeCareReportTitle"]),
        HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=14),
    ]


def _p(value, style):
    return Paragraph(escape(str(value if value is not None else "")), style)


def _styled_table(data, col_widths, *, alignments=None, danger_rows=None):
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

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
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
):
    styles = _styles()
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
        [_p("Bénéfice Net", styles["TradeCareSummaryLabel"]), _p(f"{benefice_net:.2f} {devise}", styles["TradeCareSummaryValue"])],
    ]
    story.append(_styled_table(summary_data, [8.3 * cm, 8.3 * cm], alignments={1: "RIGHT"}))

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
    story.append(_styled_table(expense_data, [2.1 * cm, 5.0 * cm, 3.2 * cm, 3.5 * cm, 2.8 * cm], alignments={0: "CENTER", 2: "RIGHT", 4: "CENTER"}))

    _document(buffer).build(
        story,
        onFirstPage=_decorate_page,
        onLaterPages=_decorate_page,
    )


def _build_expense_report(buffer, devise, depenses):
    styles = _styles()
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
    story.append(_styled_table(data, [2.1 * cm, 5.0 * cm, 3.2 * cm, 3.5 * cm, 2.8 * cm], alignments={0: "CENTER", 2: "RIGHT", 4: "CENTER"}))
    _document(buffer).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_sales_report(buffer, devise, ventes):
    styles = _styles()
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
    story.append(_styled_table(data, [1.7 * cm, 2.8 * cm, 5.1 * cm, 2.5 * cm, 2.6 * cm, 2.2 * cm], alignments={0: "CENTER", 3: "RIGHT", 4: "CENTER", 5: "CENTER"}))
    _document(buffer).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_purchase_report(buffer, devise, achats):
    styles = _styles()
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
    story.append(_styled_table(data, [2.2 * cm, 7.0 * cm, 4.0 * cm, 3.4 * cm], alignments={0: "CENTER", 2: "RIGHT", 3: "CENTER"}))
    _document(buffer).build(story, onFirstPage=_decorate_page, onLaterPages=_decorate_page)


def _build_stock_report(buffer, devise, rows):
    styles = _styles()
    body = styles["TradeCareBody"]
    center = styles["TradeCareCenter"]
    data = [["ID", "Nom du produit", "Caractéristiques", "Codes / Traçabilités", "Stock initial", "Disponible", f"Prix ({devise})"]]
    danger_rows = []
    for row in rows:
        data.append(
            [
                _p(row["id"], center),
                _p(row["name"], body),
                _p(row["characteristics"], body),
                Paragraph("<br/>".join(escape(code) for code in row["traceability"]), body),
                _p(row["initial"], center),
                _p(row["available"], center),
                _p(f"{row['price']:.2f}", body),
            ]
        )
        if row["available"] == 0:
            danger_rows.append(len(data) - 1)
    story = [*_title_block("État du Stock", styles)]
    story.append(
        _styled_table(
            data,
            [1.3 * cm, 4.6 * cm, 5.1 * cm, 5.3 * cm, 2.7 * cm, 2.7 * cm, 3.2 * cm],
            alignments={0: "CENTER", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT"},
            danger_rows=danger_rows,
        )
    )
    _document(buffer, landscape_mode=True).build(
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
    parent_user_id = (
        current_user.parent_user_id
        if not current_user.is_main_user
        else current_user.id
    )
    devise = current_user.devise or "FCFA"
    total_ventes = (
        db.query(func.sum(CommandeVente.total_ttc))
        .filter(CommandeVente.user_id == parent_user_id)
        .scalar()
        or 0
    )
    total_achats = (
        db.query(func.sum(CommandeAchat.total_ttc))
        .filter(CommandeAchat.user_id == parent_user_id)
        .scalar()
        or 0
    )
    total_depenses = (
        db.query(func.sum(Depense.montant))
        .filter(Depense.user_id == parent_user_id)
        .scalar()
        or 0
    )
    ventes = (
        db.query(CommandeVente)
        .filter(CommandeVente.user_id == parent_user_id)
        .order_by(CommandeVente.date_commande.desc())
        .all()
    )
    achats = (
        db.query(CommandeAchat)
        .filter(CommandeAchat.user_id == parent_user_id)
        .order_by(CommandeAchat.date_commande.desc())
        .all()
    )
    depenses = (
        db.query(Depense)
        .filter(Depense.user_id == parent_user_id)
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
    )
    filename = f"rapport-financier-{datetime.datetime.now().strftime('%d-%m-%Y')}.pdf"
    return _response(buffer, filename)


@router.get("/rapport-depenses")
def export_rapport_depenses(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    devise = current_user.devise or "FCFA"
    depenses = db.query(Depense).filter(Depense.user_id == parent_user_id).order_by(Depense.date_depense.desc()).all()
    buffer = BytesIO()
    _build_expense_report(buffer, devise, depenses)
    return _response(buffer, "rapport_depenses.pdf")


@router.get("/rapport-ventes")
def export_rapport_ventes(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    devise = current_user.devise or "FCFA"
    ventes = (
        db.query(CommandeVente)
        .filter(CommandeVente.user_id == parent_user_id)
        .filter(CommandeVente.statut.in_(["validée", "en_attente"]))
        .order_by(CommandeVente.date_commande.desc())
        .all()
    )
    buffer = BytesIO()
    _build_sales_report(buffer, devise, ventes)
    return _response(buffer, "rapport_ventes.pdf")


@router.get("/rapport-achats")
def export_rapport_achats(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    devise = current_user.devise or "FCFA"
    achats = db.query(CommandeAchat).filter(CommandeAchat.user_id == parent_user_id).order_by(CommandeAchat.date_commande.desc()).all()
    buffer = BytesIO()
    _build_purchase_report(buffer, devise, achats)
    return _response(buffer, "rapport_achats.pdf")


@router.get("/etat-stock")
def export_etat_stock(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.caissier])),
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    devise = current_user.devise or "FCFA"
    produits = (
        db.query(Produit)
        .filter(Produit.user_id == parent_user_id, Produit.date_suppression.is_(None))
        .order_by(Produit.nom.asc())
        .all()
    )
    traceability_by_product = defaultdict(list)
    for product_id, traceability in db.query(
        UniteProduit.produit_id, UniteProduit.tracabilite
    ).filter(UniteProduit.tracabilite.isnot(None)).all():
        traceability_by_product[product_id].append(traceability)

    rows = []
    for product in produits:
        initial_stock = db.query(UniteProduit).filter(UniteProduit.produit_id == product.id).count()
        available_stock = db.query(UniteProduit).filter(
            UniteProduit.produit_id == product.id,
            UniteProduit.statut == "disponible",
        ).count()
        rows.append(
            {
                "id": product.id,
                "name": product.nom,
                "characteristics": product.caracteristiques or "-",
                "traceability": sorted(set(traceability_by_product.get(product.id, []))) or ["-"],
                "initial": initial_stock,
                "available": available_stock,
                "price": product.prix_vente,
            }
        )

    buffer = BytesIO()
    _build_stock_report(buffer, devise, rows)
    return _response(buffer, "etat_stock.pdf")
