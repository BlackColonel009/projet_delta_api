
from sqlalchemy.orm import Session
from app.models.model_unite_produit import UniteProduit
from app.models.model_user import User
from sqlalchemy import func
from app.repo_scheduler.low_stock_pdf import generate_stock_pdf  # à créer
from app.core.mail import send_email_message  # déjà présent



from sqlalchemy import func
from app.models.model_produit import Produit
from app.models.model_user import User

from datetime import datetime, timedelta
from sqlalchemy import func
from app.core.mail import send_email_message
from app.models.model_user import User
from app.models.model_produit import Produit
from app.models.model_unite_produit import UniteProduit
from sqlalchemy.orm import Session
import os


async def run_stock_alert_scheduler(db: Session):
    now = datetime.utcnow()

    users = db.query(User).all()

    for user in users:
        # Récupérer uniquement les produits du user avec stock faible
        produits_stock_faible = (
            db.query(Produit)
            .join(UniteProduit)
            .filter(
                Produit.user_id == user.id,
                UniteProduit.statut == "disponible"
            )
            .group_by(Produit.id)
            .having(func.count(UniteProduit.id) <= Produit.stock_min)
            .all()
        )

        if not produits_stock_faible:
            continue  # Pas de produit à alerter pour cet utilisateur

        pdf_path = generate_stock_pdf(produits_stock_faible, user)

        sujet = f"Alerte stock faible - {user.societe_ou_entreprise or 'Votre société'}"
        corps = "Voici la liste des produits dont le stock est inférieur ou égal au seuil défini."

        await send_email_message(
            to_email=user.email,
            subject=sujet,
            body=corps,
            attachments=[pdf_path]
        )

        os.remove(pdf_path)
