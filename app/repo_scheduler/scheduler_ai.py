from datetime import datetime, timedelta
from io import BytesIO
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func
from app.core.mail import send_email_message
from app.email.branded_templates import (
    loyalty_email,
    payment_reminder_email,
    product_recommendation_email,
)
from app.utils.i18n import language_of, translated
from app.utils.public_url import public_url
from app.utils.color_theme import build_document_palette
from app.models.model_client_produit import ClientProduit
from app.models.model_clientfollowup import ClientFollowup, FollowupStatus
from app.utils.subscription_guard import company_has_feature
from app.core.whatsapp import send_whatsapp_message
from sqlalchemy.orm import Session
from app.models.model_commande import CommandeVente
from app.models.model_facture import Facture
from app.models.model_paiement import Paiement
from app.models.model_produit import Produit
from app.models.model_user import User
from xhtml2pdf import pisa




# def run_followup_scheduler(db: Session):
#     today = datetime.utcnow()

#     followups = db.query(ClientFollowup).filter(
#         ClientFollowup.date_prochain_envoi <= today,
#         ClientFollowup.statut != FollowupStatus.termine
#     ).all()

#     for f in followups:
#         commande = db.query(CommandeVente).filter(CommandeVente.id == f.commande_id).first()
#         if not commande:
#             continue

#         # 🔁 Vérification paiement si relance
#         if f.type_followup == "relance_paiement":
#             if commande.statut == "validée":
#                 f.statut = FollowupStatus.termine
#                 db.commit()
#                 continue

#             msg = f"🔔 Bonjour {f.client.nom},\nVotre commande #{commande.id} est toujours en attente de paiement.\nMerci de finaliser votre achat dès que possible 🙏."
#             print(msg)
#             send_whatsapp_message(f.client.telephone, msg)
#             f.date_prochain_envoi = today + timedelta(days=7)

#         elif f.type_followup == "fidélisation":
#             if f.statut == FollowupStatus.EN_ATTENTE:
#                 msg = (
#                     f"👋 Bonjour {f.client.nom},\n"
#                     "Nous espérons que le produit que vous avez commandé vous est utile 🛠️.\n"
#                     "Merci encore pour votre confiance 💚.\n"
#                     "À très bientôt !"
#                 )
#                 send_whatsapp_message(f.client.telephone, msg)
#                 f.statut = FollowupStatus.message_1_envoye
#                 f.date_prochain_envoi = today + timedelta(days=1)

#             elif f.statut == FollowupStatus.message_1_envoye:
#                 produits = get_2_random_produits(db)

#                 for p in produits:
#                     message = (
#                         f"🔥 Découvrez notre coup de cœur du moment !\n"
#                         f"🛍️ *{p.nom}*\n"
#                         f"📄 {p.description or 'Produit de qualité exceptionnelle'}\n"
#                         f"📸 Voir : {p.image_url or 'Image non disponible'}\n"
#                         f"👉 Contactez-nous pour plus d'infos !"
#                     )
#                     send_whatsapp_message(f.client.telephone, message)

#                 f.statut = FollowupStatus.message_2_envoye
#                 f.date_prochain_envoi = today + timedelta(days=7)

#             elif f.statut == FollowupStatus.message_2_envoye:
#                 f.statut = FollowupStatus.termine

#         db.commit()

# **************************************test**************************************

# def run_followup_scheduler(db: Session):
#     now = datetime.utcnow()

#     followups = db.query(ClientFollowup).filter(
#         ClientFollowup.date_prochain_envoi <= now,
#         ClientFollowup.statut != FollowupStatus.termine
#     ).all()

#     for f in followups:
#         commande = db.query(CommandeVente).filter(CommandeVente.id == f.commande_id).first()
#         if not commande:
#             continue

#         # 🔁 Vérification paiement si relance
#         if f.type_followup == "relance_paiement":
#             if commande.statut == "validée":
#                 f.statut = FollowupStatus.en_attente
#                 f.type_followup = "fidélisation"
#                 db.commit()
#                 continue

#             msg = f"🔔 [TEST] Bonjour {f.client.nom}, votre commande #{commande.id} est toujours en attente de paiement."
#             send_whatsapp_message(f.client.telephone, msg)
#             f.date_prochain_envoi = now + timedelta(days=1)

#         elif f.type_followup == "fidélisation":
#             if f.statut == FollowupStatus.en_attente:
#                 msg = f"👋 [TEST] Bonjour {f.client.nom}, merci pour votre commande !"
#                 send_whatsapp_message(f.client.telephone, msg)
#                 f.statut = FollowupStatus.message_1_envoye
#                 f.date_prochain_envoi = now + timedelta(days=1)

#             elif f.statut == FollowupStatus.message_1_envoye:
#                 produits = get_2_random_produits(db)
#                 for p in produits:
#                     msg = (
#                         f"🔥 [TEST] Produit recommandé : {p.nom}\n"
#                         f"📄 {p.caracteristiques or 'Pas de description'}\n"
#                         f"📸 {p.image_url or 'Aucune image'}"
#                     )
#                     send_whatsapp_message(f.client.telephone, msg)

#                 f.statut = FollowupStatus.message_2_envoye
#                 f.date_prochain_envoi = now + timedelta(days=1)

#             elif f.statut == FollowupStatus.message_2_envoye:
#                 f.statut = FollowupStatus.message_1_envoye

#         db.commit()

# **************************************** EMAIL ****************************************

import uuid
import os

from app.routes import facture

def generate_product_pdf(product, user):
    env = Environment(
        loader=FileSystemLoader("app/repo_scheduler"),
        autoescape=select_autoescape(['html', 'xml'])
    )
    template = env.get_template("template_product_mail.html")
    palette = build_document_palette(getattr(user, "facture_color", None))
    language = language_of(user)

    # Logo (si hébergé publiquement)
    logo_url = public_url(user.logo_entreprise)

    # Produit précis
    Produit_precis = {
        "nom": product.nom,
        "caracteristiques": product.caracteristiques or translated(language, "Aucune description disponible", "No description available"),
        "image": public_url(product.image_url),
    }

    html_content = template.render(
        lang=language,
        produit=Produit_precis,
        societe={
            "nom": user.societe_ou_entreprise,
            "adresse": user.addresse or "",
            "telephone": user.telephone,
            "email": user.email
        },
        logo_url=logo_url,
        icons={
            "location": public_url("/static/fac_icon/loc.png"),
            "account": public_url("/static/fac_icon/acc.png"),
            "phone": public_url("/static/fac_icon/tel.png"),
            "mail": public_url("/static/fac_icon/mail.png"),
        },
        theme=palette,
    )

    # Générer PDF
    filename = f"temp_{uuid.uuid4().hex}.pdf"
    filepath = os.path.join("app", "temp", filename)
    os.makedirs("app/temp", exist_ok=True)

    with open(filepath, "wb") as f:
        result = pisa.CreatePDF(html_content, dest=f)
    if result.err:
        raise Exception("Erreur lors de la génération PDF avec xhtml2pdf")

    return filepath
# <- retourne le chemin du fichier




async def run_followup_scheduler(db: Session):
    now = datetime.utcnow()
    

    followups = db.query(ClientFollowup).filter(
        ClientFollowup.date_prochain_envoi <= now,
        ClientFollowup.statut != FollowupStatus.termine
    ).all()

    
    
    for f in followups:
        user = db.query(User).filter(User.id == f.user_id).first()
        if not user or not company_has_feature(
            db,
            f.user_id,
            "client_followup",
        ):
            continue
        if not f.client or not f.client.email:
            continue

        commande = db.query(CommandeVente).filter(CommandeVente.id == f.commande_id).first()
        if not commande:
            continue

        # 🚫 Ignorer ou terminer si commande annulée
        if commande.statut == "annulée":
            f.statut = FollowupStatus.termine
            db.commit()
            continue

        # Récupérer tous les produits liés au client
        produits_client = db.query(ClientProduit).filter(
            ClientProduit.client_id == f.client_id,
            ClientProduit.commande_id == f.commande_id
        ).all()

        if f.type_followup == "relance_paiement":
            if not getattr(f, "payment_reminder_enabled", True):
                continue
            if not f.date_achat:
                continue

            date_expiration = f.date_achat + timedelta(days=f.delai_avant_relance)
            if now < date_expiration:
                continue




        # Extraire les noms des produits (backup_nom supposé exister)
        noms_produits_list = [p.nom_produit for p in produits_client]
        # Récupérer la facture liée à la commande (si tu as la facture)
        facture = db.query(Facture).filter(Facture.commande_id == commande.id).first()
        if not facture:
            continue

        devise = facture.user.devise if hasattr(facture, "user") else ""

        # Calculer le total payé via la table Paiement
        total_paye = db.query(func.coalesce(func.sum(Paiement.montant), 0))\
            .filter(Paiement.facture_id == facture.id).scalar()

        # Calculer le reste à payer
        reste = facture.total_ttc - total_paye

        # Exemple de message
        

        # 🔁 Vérification paiement si relance
        if f.type_followup == "relance_paiement":
            if commande.statut == "validée" or reste <= 0.01:
                f.statut = FollowupStatus.en_attente
                f.type_followup = "fidélisation"
                thank_you_delay = getattr(
                    f.client, "followup_thank_you_delay_days", 1
                )
                f.date_prochain_envoi = now + timedelta(days=thank_you_delay)
                db.commit()
                continue

            msg = payment_reminder_email(
                user=user,
                client_name=f.client.nom,
                order_id=commande.id,
                product_names=noms_produits_list,
                total=facture.total_ttc,
                paid=total_paye,
                balance=reste,
                currency=devise,
                order_date=commande.date_commande,
                delay_days=f.delai_avant_relance,
            )


            language = language_of(user)
            await send_email_message(
                f.client.email,
                translated(language, f"{user.societe_ou_entreprise} Relance - Commande en attente", f"{user.societe_ou_entreprise} Reminder - Pending order"),
                msg,
                reply_to=user.email if user else None,
                is_html=True,
            )
            f.date_prochain_envoi = now + timedelta(days=1)

        elif f.type_followup == "fidélisation":
            if not getattr(f.client, "followup_enabled", True):
                continue

            recommendations_enabled = getattr(
                f.client, "followup_recommendations_enabled", True
            )
            first_recommendation_delay = getattr(
                f.client, "followup_first_recommendation_delay_days", 10
            )
            recommendation_interval = getattr(
                f.client, "followup_recommendation_interval_days", 14
            )
            if f.statut == FollowupStatus.en_attente:
                msg = loyalty_email(
                    user=user,
                    client_name=f.client.nom,
                    product_names=noms_produits_list,
                )
                language = language_of(user)
                await send_email_message(
                    f.client.email,
                    translated(language, f"Merci pour votre confiance — {user.societe_ou_entreprise}", f"Thank you for your trust — {user.societe_ou_entreprise}"),
                    msg,
                    reply_to=user.email if user else None,
                    is_html=True,
                )
                f.statut = FollowupStatus.message_1_envoye
                if recommendations_enabled:
                    f.date_prochain_envoi = now + timedelta(
                        days=first_recommendation_delay
                    )
                else:
                    f.statut = FollowupStatus.termine

            elif f.statut in (
                FollowupStatus.message_1_envoye,
                FollowupStatus.message_2_envoye,
            ):
                if not recommendations_enabled or not company_has_feature(
                    db,
                    f.user_id,
                    "product_recommendation",
                ):
                    f.statut = FollowupStatus.termine
                    db.commit()
                    continue
                produits = get_2_random_produits(db, f.user_id)
                for p in produits:
                    # Génére le PDF en mémoire
                    # pdf_buffer = generate_product_pdf(p, user)
                    filename = f"{p.nom}.pdf"

                    msg = product_recommendation_email(
                        user=user,
                        client_name=f.client.nom,
                        product=p,
                    )
                  

                    pdf_path = generate_product_pdf(p, user)

                    language = language_of(user)
                    await send_email_message(
                        f.client.email,
                        translated(language, f"Notre sélection pour vous : {p.nom}", f"Our selection for you: {p.nom}"),
                        msg,
                        reply_to=user.email if user else None,
                        attachments=[pdf_path],  # chemin absolu ou relatif du fichier
                        is_html=True,
                    )
                    os.remove(pdf_path)



                f.statut = FollowupStatus.message_2_envoye
                f.date_prochain_envoi = now + timedelta(
                    days=recommendation_interval
                )

        db.commit()

# Simule la récupération de 2 produits aléatoires
def get_2_random_produits(db: Session, user_id: int):
    return (
        db.query(Produit)
        .filter(
            Produit.image_url != None,
            Produit.user_id == user_id  # filtre sur l'utilisateur connecté
        )
        .order_by(func.random())
        .limit(2)
        .all()
    )
