# 📁 app/routes/reset.py
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from uuid import uuid4
from app.database import get_db
from app.models import model_categorie, model_facture, model_historique_intervention, model_intervention, model_paiement, model_unite_produit, model_user
from app.models.model_client_produit import ClientProduit
from app.models.model_user import User
from app.schemas.reset_schema import ResetCodeSchema
from app.models import model_client, model_fournisseur, model_produit, model_commande, model_rapport
from app.models.model_reset_token import ResetToken
from app.utils.logger import log_action
from app.utils.reset_token import generate_code, save_code, send_reset_email
from app.utils.security import get_current_user, hash_password
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.config import conf
import random

router = APIRouter(prefix="/reset", tags=["Réinitialisation"])

# ➕ Étape 1 : envoyer le code de confirmation par email
@router.post("/request")
async def request_reset_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # code = str(uuid4()).split("-")[0].upper()
    
    code = str(random.randint(100000, 999999))  # 6 chiffres

    db.add(ResetToken(user_id=current_user.id, code=code))
    db.commit()

    message = MessageSchema(
        subject="Code de réinitialisation de votre compte",
        recipients=[current_user.email],
        body=f"Bonjour {current_user.email},\n\nVoici votre code de réinitialisation : {code}",
        subtype=MessageType.plain,
    )
    fm = FastMail(conf)
    await fm.send_message(message)

    return {"message": "Code de confirmation envoyé par email."}


# ✅ Étape 2 : vérifier le code et réinitialiser le compte
@router.post("/verify")
def verify_reset_code(
    data: ResetCodeSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    code = data.code
    token = db.query(ResetToken).filter(
        ResetToken.user_id == current_user.id,
        ResetToken.code == code
    ).first()

    if not token:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    # Récupérer l'ID utilisateur
    user_id = current_user.id

    # 1️⃣ Supprimer les paiements liés aux factures de cet utilisateur
    db.query(model_paiement.Paiement).filter(
        model_paiement.Paiement.facture_id.in_(
            db.query(model_facture.Facture.id).filter(
                (model_facture.Facture.client_id.in_(
                    db.query(model_client.Client.id).filter_by(user_id=user_id)
                )) |
                (model_facture.Facture.fournisseur_id.in_(
                    db.query(model_fournisseur.Fournisseur.id).filter_by(user_id=user_id)
                ))
            )
        )
    ).delete(synchronize_session=False)
    
    db.query(model_facture.LigneFacture).filter(
        model_facture.LigneFacture.facture_id.in_(
            db.query(model_facture.Facture.id).filter(
                (model_facture.Facture.client_id.in_(
                    db.query(model_client.Client.id).filter_by(user_id=user_id)
                )) |
                (model_facture.Facture.fournisseur_id.in_(
                    db.query(model_fournisseur.Fournisseur.id).filter_by(user_id=user_id)
                ))
            )
        )
    ).delete(synchronize_session=False)

    # 2️⃣ Supprimer les factures
    db.query(model_facture.Facture).filter(
        (model_facture.Facture.client_id.in_(
            db.query(model_client.Client.id).filter_by(user_id=user_id)
        )) |
        (model_facture.Facture.fournisseur_id.in_(
            db.query(model_fournisseur.Fournisseur.id).filter_by(user_id=user_id)
        ))
    ).delete(synchronize_session=False)
    
    # 🖼 Supprimer les galeries liées aux produits de ce user
    db.query(model_produit.GaleriePhoto).filter(
        model_produit.GaleriePhoto.produit_id.in_(
            db.query(model_produit.Produit.id).filter_by(user_id=user_id)
        )
    ).delete(synchronize_session=False)

    
    # 2️⃣ BIS Supprimer les lignes des commandes de ventes liées à ce user
    db.query(model_commande.LigneCommandeVente).filter(
        model_commande.LigneCommandeVente.commande_id.in_(
            db.query(model_commande.CommandeVente.id).filter(
                model_commande.CommandeVente.client_id.in_(
                    db.query(model_client.Client.id).filter_by(user_id=user_id)
                )
            )
        )
    ).delete(synchronize_session=False)

    # 🔥 Supprimer les unités produits liées à des commandes ventes de ce user
    db.query(model_unite_produit.UniteProduit).filter(
        model_unite_produit.UniteProduit.commande_vente_id.in_(
            db.query(model_commande.CommandeVente.id).filter(
                model_commande.CommandeVente.client_id.in_(
                    db.query(model_client.Client.id).filter_by(user_id=user_id)
                )
            )
        )
    ).delete(synchronize_session=False)


    # 3️⃣ Supprimer commandes ventes et achats
    db.query(model_commande.CommandeVente).filter(
        model_commande.CommandeVente.client_id.in_(
            db.query(model_client.Client.id).filter_by(user_id=user_id)
        )
    ).delete(synchronize_session=False)

    db.query(model_commande.CommandeAchat).filter(
        model_commande.CommandeAchat.fournisseur_id.in_(
            db.query(model_fournisseur.Fournisseur.id).filter_by(user_id=user_id)
        )
    ).delete(synchronize_session=False)
    
    # 🔥 4. Supprimer interventions et historique_intervention
    db.query(model_historique_intervention.HistoriqueIntervention).filter(
        model_historique_intervention.HistoriqueIntervention.user_id == user_id
    ).delete(synchronize_session=False)

    db.query(model_intervention.Intervention).filter(
        model_intervention.Intervention.user_id == user_id
    ).delete(synchronize_session=False)

    # 🔥 5. Supprimer unités-produits liées aux produits de ce user
    db.query(model_unite_produit.UniteProduit).filter(
        model_unite_produit.UniteProduit.produit_id.in_(
            db.query(model_produit.Produit.id).filter_by(user_id=user_id)
        )
    ).delete(synchronize_session=False)

    db.query(ClientProduit).filter(
        ClientProduit.client_id.in_(
            db.query(model_client.Client.id).filter_by(user_id=user_id)
        )
    ).delete(synchronize_session=False)

    # 4️⃣ Supprimer le reste
    db.query(model_client.Client).filter_by(user_id=user_id).delete()
    db.query(model_produit.Produit).filter_by(user_id=user_id).delete()
    db.query(model_fournisseur.Fournisseur).filter_by(user_id=user_id).delete()
    db.query(model_rapport.Rapport).filter_by(user_id=user_id).delete()
    # db.query(model_user.SubUser).filter_by(parent_user_id=user_id).delete()
    db.query(model_categorie.Categorie).filter_by(user_id=user_id).delete()
    
    db.delete(token)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Réinitialisation du compte",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Suppression de toutes les données liées à l'utilisateur sauf son profil principal."
    )
    
    
    db.commit()

    return {"message": "Votre compte a été réinitialisé avec succès."}


#Reset Password 

@router.post("/forgot-password")
def forgot_password(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email non trouvé")

    code = generate_code()
    save_code(db, user.id, code)
    send_reset_email(user.email, code)

    return {"message": "Code envoyé à votre email"}

@router.post("/reset-password")
def reset_password(
    email: str = Body(...),
    code: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    token = db.query(ResetToken).filter(
        ResetToken.user_id == user.id,
        ResetToken.code == code
    ).first()

    if not token:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    # 🔐 Mise à jour du mot de passe correctement
    user.password_hash = hash_password(new_password)

    db.delete(token)
    db.commit()

    return {"message": "Mot de passe réinitialisé avec succès"}
