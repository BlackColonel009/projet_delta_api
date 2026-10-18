from io import BytesIO
from typing import Optional
from fastapi import Depends
from sqlalchemy.orm import Session
from pathlib import Path
from jinja2 import Environment, select_autoescape, FileSystemLoader
from xhtml2pdf import pisa
from app.models.model_facture import Facture, LigneFacture
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import SubUser, User
from app.utils.public_url import document_asset_url
from app.utils.color_theme import build_document_palette
from app.utils.security import get_current_sub_user
from app.utils.i18n import language_of
from datetime import datetime
from app.services.invoice_snapshot_service import (
    invoice_snapshot_values,
    validate_official_invoice_date,
)
from app.services.invoice_template_registry import TEMPLATES_BY_CODE
from app.services.invoice_line_snapshot_service import serialize_characteristics
import re
import tempfile


from app.models.model_facture import TypeFacture  # Assure-toi que cet import est présent

import json

def safe_parse_caracteristiques(caract):
    if isinstance(caract, str):
        try:
            return json.loads(caract)
        except Exception:
            # Ce n'est pas un JSON valide, on garde la chaîne brute (string)
            return caract
    elif caract is None:
        return {}
    else:
        return caract


def generate_facture_from_commande(
    db: Session,
    commande,
    commande_type: str,
    current_sub: Optional[SubUser] = None,
    professional_invoice: bool = True,
    current_actor=None,
    official_date: datetime | None = None,
):
    actor = current_actor or current_sub
    sub_user_id = actor.id if isinstance(actor, SubUser) else None
    issuer = actor or db.query(User).filter(User.id == commande.user_id).first()
    snapshot = invoice_snapshot_values(db, issuer, commande.enterprise_id)

    # Définition sécurisée de type_enum à partir de commande.statut ou fallback
    if isinstance(commande.statut, str) and commande.statut in TypeFacture._value2member_map_:
        type_enum = TypeFacture(commande.statut)
    else:
        type_enum = TypeFacture(commande_type)

    facture = Facture(
        type=type_enum,
        client_id=commande.client_id if commande_type == "vente" else None,
        fournisseur_id=commande.fournisseur_id if commande_type == "achat" else None,
        total_ht=commande.total_ht,
        tva=commande.tva,
        total_ttc=commande.total_ttc,
        user_id=commande.user_id,
        enterprise_id=commande.enterprise_id,
        sub_user_id=sub_user_id,
        date_creation=validate_official_invoice_date(official_date),
        technical_created_at=datetime.utcnow(),
        commande_id=commande.id if commande_type == "vente" else None,
        commande_achat_id=commande.id if commande_type == "achat" else None,
        **snapshot,
    )
    db.add(facture)
    db.commit()
    db.refresh(facture)

    for ligne in commande.lignes:
        db.add(LigneFacture(
            facture_id=facture.id,
            produit_id=ligne.produit_id,
            description=ligne.description,
            caracteristiques_snapshot=serialize_characteristics(
                getattr(getattr(ligne, "produit", None), "caracteristiques", None)
            ),
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            cout_achat_unitaire=(
                float(ligne.cout_achat_unitaire or 0)
                if commande_type == "vente"
                else float(ligne.prix_unitaire or 0)
            ),
            total_ligne=ligne.total_ligne,
            enterprise_id=commande.enterprise_id,
        ))

    db.commit()

    # La facture est créée, mais jamais générée ni envoyée automatiquement.
    # L'utilisateur choisit ensuite explicitement le format et l'envoi depuis
    # l'application. Cela évite également de bloquer la vente sur SMTP/PDF.
    return facture

from app.utils.amount_in_words import amount_to_words


def generate_facture_pdf(facture, db: Session ):
    devise = facture.user.devise or "XOF"
    language = language_of(facture.sub_user or facture.user)
    montant_en_lettres = amount_to_words(facture.total_ttc, devise, language)
    logo_url = document_asset_url(facture.user.logo_entreprise)

    template_directory = Path(__file__).resolve().parent.parent / "template"
    env = Environment(
        loader=FileSystemLoader(str(template_directory)),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters["parse_characteristics"] = safe_parse_caracteristiques
    template = env.get_template("facture_template.html")

    vendeur = {
        "nom": getattr(facture, "issuer_name_snapshot", None)
        or (
            facture.sub_user.username
            if getattr(facture, "sub_user", None)
            else facture.user.societe_ou_entreprise or facture.user.email
        ),
        "poste": getattr(facture, "issuer_role_snapshot", None)
        or (
            facture.sub_user.role
            if getattr(facture, "sub_user", None)
            else "Administrateur"
        ),
    }

    # Ajout des unités concernées sans modifier les produits persistés.
    for ligne in facture.lignes:
        produit = ligne.produit
        if produit:
            unit_filters = [UniteProduit.produit_id == produit.id]
            if facture.commande_id:
                unit_filters.append(
                    UniteProduit.commande_vente_id == facture.commande_id
                )
            elif facture.commande_achat_id:
                unit_filters.append(
                    UniteProduit.commande_achat_id == facture.commande_achat_id
                )
            ligne.unites = (
                db.query(UniteProduit).filter(*unit_filters).all()
                if len(unit_filters) > 1
                else []
            )

    palette = build_document_palette(
        getattr(facture, "invoice_color_snapshot", None)
        or facture.user.facture_color,
        fallback="#5C6BC0",
    )

    template_code = (
        getattr(facture, "professional_template_snapshot", None)
        or "professional_signature"
    )
    template_definition = TEMPLATES_BY_CODE.get(template_code)
    if not template_definition or template_definition.family != "professional":
        template_code = "professional_signature"



    html_content = template.render(
        lang=language,
        devise=devise,
        facture=facture,
        societe={
            "nom": facture.user.societe_ou_entreprise,
            "adresse": facture.user.addresse or "",# ✅ corrigé ici
            "nif": facture.user.nif or "",  # ✅ corrigé ici
            "tva": facture.user.tva or 0.18,  # ✅ corrigé ici
            "telephone": facture.user.telephone,
            "email": facture.user.email
        },
        vendeur=vendeur,
        show_agent_name=getattr(
            getattr(facture, "enterprise", None), "show_invoice_agent", True
        ),
        logo_url=logo_url,
        montant_en_lettres=montant_en_lettres,
        color_background=palette["primary_pale"],
        color_text=palette["primary"],
        color_dark=palette["primary_dark"],
        color_highlight=palette["primary_soft"],
        color_on_primary=palette["on_primary"],
        template_code=template_code,
    )

    buffer = BytesIO()
    pdf_result = pisa.CreatePDF(html_content, dest=buffer)
    if pdf_result.err:
        raise RuntimeError("La facture professionnelle n'a pas pu être générée.")
    buffer.seek(0)

    # Nettoyer nom du client
    destinataire = facture.client or facture.fournisseur
    client_nom = (
        re.sub(r'\W+', '_', destinataire.nom.strip())
        if destinataire
        else "SansDestinataire"
    )

    # Type de facture
    facture_type = facture.type or "facture"

    # Date/heure
    date_str = datetime.now().strftime("%Y%m%d_%H%M")

    prefix = re.sub(r'\W+', '_', f"{facture_type}_{client_nom}_{date_str}")
    with tempfile.NamedTemporaryFile(
        mode="wb",
        prefix=f"{prefix}_",
        suffix=".pdf",
        delete=False,
    ) as pdf_file:
        pdf_file.write(buffer.getvalue())
        return pdf_file.name

