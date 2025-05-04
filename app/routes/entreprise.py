from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.model_user import User
from app.models.model_produit import Produit
from app.models.model_commande import CommandeVente
from app.utils.security import get_current_user, require_main_user

router = APIRouter(prefix="/entreprise", tags=["Entreprise"])

# 🏢 Infos basiques sur l'entreprise
@router.get("/info")
def get_entreprise_info(
    db: Session = Depends(get_db),
    current_user=Depends(require_main_user)
):
    if not current_user.is_main_user:
        raise HTTPException(status_code=403, detail="Seul le compte principal peut accéder aux informations d'entreprise.")

    societe = current_user.societe_ou_entreprise

    # 👤 Nombre total d'utilisateurs liés (main + subusers)
    total_utilisateurs = db.query(User).filter(
        (User.email == current_user.email) | (User.parent_email == current_user.email)
    ).count()

    # 📦 Nombre total de produits créés par l'entreprise
    total_produits = db.query(Produit).filter(
        Produit.created_by == current_user.email
    ).count()

    # 💰 Chiffre d'affaires total
    chiffre_affaires = db.query(func.sum(CommandeVente.total_ttc)).filter(
        CommandeVente.parent_email == current_user.email
    ).scalar() or 0

    return {
        "societe": societe,
        "total_utilisateurs": total_utilisateurs,
        "total_produits": total_produits,
        "chiffre_affaires": round(chiffre_affaires, 2)
    }

# 📊 Infos complètes sur l’entreprise
@router.get("/info/complete")
def get_entreprise_info_complete(
    db: Session = Depends(get_db),
    current_user=Depends(require_main_user)
):
    if not current_user.is_main_user:
        raise HTTPException(status_code=403, detail="Seul le compte principal peut accéder aux informations d'entreprise.")

    societe = current_user.societe_ou_entreprise

    # 👥 Tous les utilisateurs liés à l’entreprise
    utilisateurs = db.query(User).filter(
        (User.email == current_user.email) | (User.parent_email == current_user.email)
    ).all()

    utilisateurs_list = [
        {
            "id": user.id,
            "email": user.email,
            "username": getattr(user, "username", None),
            "role": getattr(user, "role", None),
            "is_main_user": user.is_main_user
        }
        for user in utilisateurs
    ]

    # 🆕 10 derniers produits ajoutés par l’entreprise
    produits = db.query(Produit).filter(
        Produit.created_by == current_user.email
    ).order_by(Produit.date_creation.desc()).limit(10).all()

    produits_list = [
        {
            "id": p.id,
            "nom": p.nom,
            "categorie": p.categorie,
            "prix_vente": p.prix_vente,
            "quantite": p.quantite,
            "date_creation": p.date_creation.strftime("%d/%m/%Y")
        }
        for p in produits
    ]

    # 🧾 10 dernières ventes réalisées
    ventes = db.query(CommandeVente).filter(
        CommandeVente.parent_email == current_user.email
    ).order_by(CommandeVente.date_commande.desc()).limit(10).all()

    ventes_list = [
        {
            "id": v.id,
            "client": v.client.nom if v.client else None,
            "total_ttc": v.total_ttc,
            "date_commande": v.date_commande.strftime("%d/%m/%Y")
        }
        for v in ventes
    ]

    # 📈 Chiffre d’affaires global
    chiffre_affaires = db.query(func.sum(CommandeVente.total_ttc)).filter(
        CommandeVente.parent_email == current_user.email
    ).scalar() or 0

    return {
        "societe": societe,
        "total_utilisateurs": len(utilisateurs_list),
        "utilisateurs": utilisateurs_list,
        "total_produits": len(produits_list),
        "produits_recents": produits_list,
        "dernieres_ventes": ventes_list,
        "chiffre_affaires": round(chiffre_affaires, 2)
    }
