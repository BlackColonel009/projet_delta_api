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
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import SubUser, User
from app.config import conf
from app.utils.public_url import public_url
from app.utils.color_theme import build_document_palette
from app.utils.security import get_current_sub_user
from datetime import datetime
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
    current_sub: Optional[SubUser] = None
):
    sub_user_id = current_sub.id if current_sub else None

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

    tmp_path = generate_facture_pdf(facture, db)

    if type_enum in [TypeFacture.vente, TypeFacture.proforma] and facture.client and facture.client.email:
        fm = FastMail(conf)
        message = MessageSchema(
            subject=f"Votre {type_enum.value.upper()} #{facture.id}",
            recipients=[facture.client.email],
            body=f"Bonjour {facture.client.nom},\n\nVeuillez trouver votre {type_enum.value.upper()} #{facture.id} d'un montant total de {facture.total_ttc:.2f} {facture.devise}.\nMerci pour votre confiance.",
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

from num2words import num2words

def montant_to_words(montant: float, devise="FCFA"):
    devise_lettres = {
        "FCFA": "francs CFA",
        "XOF": "francs CFA",
        "EUR": "euros",
        "€": "euros",
        "USD": "dollars",
        "$": "dollars",
        "GBP": "livres sterling",
        "£": "livres sterling",
        "JPY": "yens",
        "¥": "yens",
        "CAD": "dollars canadiens",
        "AUD": "dollars australiens",
        "CHF": "francs suisses",
        "CNY": "yuans chinois",
        "INR": "roupies indiennes",
        "RUB": "roubles russes",
        "BRL": "réals brésiliens",
        "ZAR": "rands sud-africains",
    }
    try:
        mots = num2words(montant, lang='fr')
        devise_texte = devise_lettres.get(devise.upper(), devise)
        return mots.capitalize() + f" {devise_texte}"
    except Exception:
        return f"{montant:.2f} {devise}"


def generate_facture_pdf(facture, db: Session ):
    devise = facture.user.devise or "XOF"
    montant_en_lettres = montant_to_words(facture.total_ttc, devise)
    logo_url = public_url(facture.user.logo_entreprise)

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

    import json

    # Convertir les caractéristiques de chaque ligne en dict (si possible)
    # 🔁 Normalisation des données ligne par ligne
   # 🧠 Ajout manuel des unités concernées pour chaque ligne
    for ligne in facture.lignes:
        produit = ligne.produit
        if produit:
            caract = produit.caracteristiques
            print("🔍 Produit:", produit.nom)
            print("📦 Type de caracteristiques:", type(caract))
            print("📄 Valeur de caracteristiques:", caract)

            # Assigner les unités concernées (liées à la commande vente)
            ligne.unites = db.query(UniteProduit).filter(
                UniteProduit.produit_id == produit.id,
                UniteProduit.commande_vente_id == facture.commande_id
            ).all()

            # Utiliser la fonction safe pour parser ou garder string
            produit.caracteristiques = safe_parse_caracteristiques(produit.caracteristiques)


    palette = build_document_palette(
        facture.user.facture_color,
        fallback="#5C6BC0",
    )



    html_content = template.render(
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
        logo_url=logo_url,
        montant_en_lettres=montant_en_lettres,
        color_background=palette["primary_pale"],
        color_text=palette["primary"],
        color_dark=palette["primary_dark"],
        color_highlight=palette["primary_soft"],
        color_on_primary=palette["on_primary"],
    )

    buffer = BytesIO()
    pisa.CreatePDF(html_content, dest=buffer)
    buffer.seek(0)



    

    # Récupérer le dossier temporaire correct (Windows/Linux/Mac)
    temp_dir = tempfile.gettempdir()

    # Nettoyer nom du client
    client_nom = (
        re.sub(r'\W+', '_', facture.client.nom.strip()) if facture.client else "SansClient"
    )

    # Type de facture
    facture_type = facture.type or "facture"

    # Date/heure
    date_str = datetime.now().strftime("%Y%m%d_%H%M")

    # Nom final
    filename = f"{facture_type}_{client_nom}_{date_str}.pdf"

    # Chemin final du fichier
    temp_path = os.path.join(temp_dir, filename)

    # Sauvegarde PDF
    with open(temp_path, "wb") as f:
        f.write(buffer.getvalue())

    return temp_path

