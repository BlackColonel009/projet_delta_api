from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO

from app.models.model_produit import Produit

def generate_stock_pdf(produits: list[Produit], user) -> str:
    """
    Génère un PDF listant les produits en stock faible et retourne le chemin vers le fichier PDF créé.
    """

    # Préparer les données sous forme de liste de dicts (ou liste de listes)
    data = []
    for p in produits:
        data.append({
            "Produit": p.nom,
            "Catégorie": p.categorie.nom if p.categorie else "N/A",
            "Stock disponible": sum(
                1 for unite in p.unites if unite.statut == "disponible"
            )
        })

    # Construire le PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = [Paragraph("Liste des stocks faibles", styles['Title'])]

    if not data:
        elements.append(Paragraph("Aucun produit en stock faible.", styles['Normal']))
    else:
        # Construire table : première ligne = headers
        table_data = [list(data[0].keys())]
        for row in data:
            table_data.append(list(row.values()))

        # Créer le tableau avec largeur automatique des colonnes
        table = Table(table_data, colWidths='*', hAlign='LEFT')  # ← ici la largeur
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 24))


    # ✅ Texte ajouté en bas du PDF
        elements.append(
            Paragraph(
                " Veuillez contacter s'il vous plaît votre fournisseur avant de nouvelles demandes de vos clients.",
                styles["Normal"]
            )
        )

    doc.build(elements)

    # Sauvegarder le buffer dans un fichier temporaire
    pdf_filename = f"stock_faible_{user.id}.pdf"
    pdf_path = f"app/temp/{pdf_filename}"

    with open(pdf_path, "wb") as f:
        f.write(buffer.getvalue())

    buffer.close()

    return pdf_path
