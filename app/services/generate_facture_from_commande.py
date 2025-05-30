from io import BytesIO
from typing import Optional
from fastapi import Depends
from sqlalchemy.orm import Session
import os
from tempfile import NamedTemporaryFile
from jinja2 import Environment, select_autoescape, FileSystemLoader
from xhtml2pdf import pisa
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.models.model_facture import Facture, LigneFacture
from app.models.model_user import SubUser, User
from app.config import conf, settings
from app.utils.security import get_current_sub_user


def generate_facture_from_commande(
    db: Session,
    commande,
    commande_type: str,
    current_sub: Optional[SubUser] = None
):
    sub_user_id = current_sub.id if current_sub else None

    facture = Facture(
        type=commande_type,
        client_id=commande.client_id if commande_type == "vente" else None,
        fournisseur_id=commande.fournisseur_id if commande_type == "achat" else None,
        total_ht=commande.total_ht,
        tva=commande.tva,
        total_ttc=commande.total_ttc,
        user_id=commande.user_id,
        sub_user_id=sub_user_id,
        commande_id=commande.id if commande_type == "vente" else None,
        commande_achat_id=commande.id if commande_type == "achat" else None,
    )
    db.add(facture)
    db.commit()
    db.refresh(facture)

    for ligne in commande.lignes:
        db.add(LigneFacture(
            facture_id=facture.id,
            produit_id=ligne.produit_id,
            description=ligne.description,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            total_ligne=ligne.total_ligne
        ))

    db.commit()

    # Générer et stocker le PDF temporairement
    tmp_path = generate_facture_pdf(facture)

    if commande_type == "vente" and facture.client and facture.client.email:
        fm = FastMail(conf)
        message = MessageSchema(
            subject=f"Votre facture #{facture.id}",
            recipients=[facture.client.email],
            body=f"Bonjour {facture.client.nom},\n\nVeuillez trouver votre facture #{facture.id} d'un montant total de {facture.total_ttc:.2f} {facture.devise}.\nMerci pour votre confiance.",
            subtype=MessageType.plain,
            attachments=[tmp_path]
        )
        try:
            import asyncio
            asyncio.run(fm.send_message(message))
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email : {e}")

    os.remove(tmp_path)
    return facture


def generate_facture_pdf(facture):
    devise = facture.user.devise or "€"
    logo_url = f"{settings.DOMAIN}{facture.user.logo_entreprise}" if facture.user.logo_entreprise else "file:///absolute/path/to/logo.png"

    env = Environment(
        loader=FileSystemLoader("app/template"),
        autoescape=select_autoescape(['html', 'xml'])
    )
    template = env.get_template("facture_template.html")

    vendeur = {
        "nom": facture.sub_user.username,
        "poste": facture.sub_user.role
    } if hasattr(facture, "sub_user") and facture.sub_user else {
        "nom": facture.user.societe_ou_entreprise or facture.user.email,
        "poste": "Administrateur"
    }

    html_content = template.render(
        devise=devise,
        facture=facture,
        societe={
            "nom": facture.user.societe_ou_entreprise,
            "adresse": facture.user.addresse or "",# ✅ corrigé ici
            "telephone": facture.user.telephone,
            "email": facture.user.email
        },
        vendeur=vendeur,
        logo_url=logo_url
    )

    buffer = BytesIO()
    pisa.CreatePDF(html_content, dest=buffer)
    buffer.seek(0)

    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(buffer.getvalue())
        return tmp.name
