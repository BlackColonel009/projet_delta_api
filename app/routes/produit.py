import json
from fastapi import APIRouter, Depends, HTTPException, Body, File, Form, UploadFile 
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.model_produit import Produit
from app.schemas.produit_schema import ProduitCreate, ProduitOut
from pydantic import BaseModel
from datetime import datetime
from app.utils.logger import log_action
from app.utils.permissions import All_required, check_role
from app.utils.security import get_current_user
from app.models.model_user import User
from app.schemas.user_schema import RoleEnum
from app.models.model_unite_produit import UniteProduit
import shutil
import os

router = APIRouter(prefix="/produits", tags=["Produits"])

@router.post("/", response_model=dict)
def create_produit(
    nom: str = Form(...),
    categorie_id: int = Form(...),
    prix_achat: float = Form(...),
    prix_vente: float = Form(...),
    quantite: int = Form(...),
    fournisseur_id: Optional[int] = Form(None),
    rating: Optional[float] = Form(None),
    caracteristiques: Optional[str] = Form(None),
    couleur: Optional[str] = Form(None),
    etat: Optional[str] = Form("oui"),
    commentaire: Optional[str] = Form(None),
    is_installe: Optional[bool] = Form(False),
    emplacement: Optional[str] = Form("magasin"),
    image: UploadFile = File(...),
    # scanned_barcodes: Optional[List[str]] = Form(None),
    scanned_barcodes_raw: Optional[str] = Form(None),

    # nombre_unites: Optional[int] = Form(0),  # ✅ nouveau champ pour auto
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    try:
        # 📷 Enregistrement de l'image
        ext = image.filename.split(".")[-1]
        image_filename = f"{datetime.utcnow().timestamp()}.{ext}"
        upload_dir = os.path.join(os.getcwd(), "upload", "produits")
        os.makedirs(upload_dir, exist_ok=True)
        image_path = os.path.join(upload_dir, image_filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # 🧱 Création du produit (sans champ quantite ni tracabilite)
        produit = Produit(
            nom=nom,
            categorie_id=categorie_id,
            prix_achat=prix_achat,
            prix_vente=prix_vente,
            fournisseur_id=fournisseur_id,
            quantite=quantite,
            rating=rating,
            caracteristiques=caracteristiques,
            couleur=couleur,
            etat=etat,
            commentaire=commentaire,
            is_installe=is_installe,
            emplacement=emplacement,
            image_url=f"/static/produits/{image_filename}",
            user_id=parent_user_id,
            a_des_barcodes=False
        )

        db.add(produit)
        db.commit()
        db.refresh(produit)
        
        # Parse les codes-barres s'ils existent
        scanned_barcodes = []
        if scanned_barcodes_raw:
            try:
                scanned_barcodes = json.loads(scanned_barcodes_raw)
            except:
                raise HTTPException(status_code=400, detail="Format JSON invalide pour scanned_barcodes")


        # 🔍 Gestion des unités : SCAN manuel
        if scanned_barcodes and len(scanned_barcodes) > 0:
            unites = []
            for code in scanned_barcodes:
                exists = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
                if exists:
                    print(f"⚠️ Doublon ignoré : {code}")
                    continue

                unites.append(UniteProduit(
                    produit_id=produit.id,
                    tracabilite=code,
                    code_barre=code,
                    statut="disponible"
                ))

            if unites:
                db.add_all(unites)
                produit.a_des_barcodes = True
                
                # ✅ AJOUTE CETTE LIGNE ICI
                produit.quantite = len(unites)
                
                db.commit()
                db.refresh(produit)

                log_action(
                    db=db,
                    current_user=current_user,
                    action="Ajout produit avec codes-barres",
                    type_entite="produit",
                    entite_id=produit.id,
                    details=f"{len(unites)} unités scannées ajoutées au produit {produit.nom}"
                )

        # ⚙️ Sinon : génération automatique par nombre
        elif quantite  > 0:
            for i in range(1, quantite  + 1):
                qr_code = f"TRAC-{produit.id}-{str(i).zfill(4)}"
                unite = UniteProduit(
                    produit_id=produit.id,
                    tracabilite=qr_code,
                    code_barre=None,
                    statut="disponible"
                )
                db.add(unite)

            db.commit()

            log_action(
                db=db,
                current_user=current_user,
                action="Ajout produit avec QR auto",
                type_entite="produit",
                entite_id=produit.id,
                details=f"{quantite} unités générées avec QR pour produit {produit.nom}"
            )

        return {"message": "Produit créé avec succès", "produit_id": produit.id}

    except Exception as e:
        db.rollback()
        db.expunge_all()
        print("❌ ERREUR lors de la création du produit :", str(e))
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du produit")




# 📋 Lister tous les produits actifs
@router.get("/", response_model=List[ProduitOut])
def list_produits(
    db: Session = Depends(get_db),
    current_user=Depends(All_required())
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    return db.query(Produit).filter(Produit.date_suppression == None, Produit.user_id == parent_user_id).all()

# 🔍 Voir un produit par ID
@router.get("/{produit_id}", response_model=ProduitOut)
def get_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        Produit.date_suppression == None,
        Produit.user_id == current_user.id  # ✅ filtre par propriétaire
    ).first()

    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    return produit



# 🔄 Modifier un produit
@router.put("/{produit_id}/", response_model=dict)
def update_produit(
    produit_id: int,
    nom: str = Form(...),
    categorie_id: int = Form(...),
    prix_achat: float = Form(...),
    prix_vente: float = Form(...),
    fournisseur_id: Optional[int] = Form(None),
    quantite: int = Form(...),
    rating: Optional[float] = Form(None),
    caracteristiques: Optional[str] = Form(None),
    couleur: Optional[str] = Form(None),
    etat: Optional[str] = Form("oui"),
    commentaire: Optional[str] = Form(None),
    is_installe: Optional[bool] = Form(False),
    # tracabilite: Optional[str] = Form(None),
    emplacement: Optional[str] = Form("magasin"),
    scanned_barcodes: Optional[str] = Form(None),  # format JSON
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # 📷 Mise à jour de l'image si fournie
    if image:
        if produit.image_url:
            old_path = produit.image_url.replace("/static", "upload")
            old_abs_path = os.path.join(os.getcwd(), old_path)
            if os.path.exists(old_abs_path):
                os.remove(old_abs_path)

        ext = image.filename.split(".")[-1]
        image_filename = f"{datetime.utcnow().timestamp()}.{ext}"
        upload_dir = os.path.join(os.getcwd(), "upload", "produits")
        image_path = os.path.join(upload_dir, image_filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        produit.image_url = f"/static/produits/{image_filename}"

    # 📝 Mise à jour des champs
    produit.nom = nom
    produit.categorie_id = categorie_id
    produit.prix_achat = prix_achat
    produit.prix_vente = prix_vente
    produit.fournisseur_id = fournisseur_id
    produit.quantite = quantite
    produit.rating = rating
    produit.caracteristiques = caracteristiques
    produit.couleur = couleur
    produit.etat = etat
    produit.commentaire = commentaire
    produit.is_installe = is_installe
    # produit.tracabilite = tracabilite
    produit.emplacement = emplacement
    produit.date_modification = datetime.utcnow()

    # ➕ Ajout de nouveaux codes-barres si fournis
    if scanned_barcodes:
        try:
            barcodes = json.loads(scanned_barcodes)
            new_count = 0
            for code in barcodes:
                exists = db.query(UniteProduit).filter(UniteProduit.code_barre == code).first()
                if not exists:
                    new_unite = UniteProduit(
                        produit_id=produit.id,
                        tracabilite=code,
                        code_barre=code,
                        statut="disponible"
                    )
                    db.add(new_unite)
                    new_count += 1

            if new_count > 0:
                produit.a_des_barcodes = True
                produit.quantite += new_count

                log_action(
                    db=db,
                    current_user=current_user,
                    action="Ajout unités lors update",
                    type_entite="produit",
                    entite_id=produit.id,
                    details=f"{new_count} unités ajoutées manuellement (update)"
                )
        except:
            raise HTTPException(status_code=400, detail="Format JSON invalide pour scanned_barcodes")

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Modification Produit",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit de nom: {produit.nom} mis à jour (avec ou sans image)"
    )

    return {"message": "Produit modifié avec succès."}

# ❌ Suppression logique d'un produit
@router.delete("/{produit_id}")
def delete_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    # 🧼 Suppression logique du produit
    produit.date_suppression = datetime.utcnow()

    # 🗑 Suppression physique des unités associées
    db.query(UniteProduit).filter(UniteProduit.produit_id == produit.id).delete()

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression Produit + Unités",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit {produit.nom} supprimé logiquement, unités supprimées définitivement"
    )

    return {"message": "Produit supprimé et unités effacées"}


# 📋 Voir les produits supprimés
@router.get("/supprimes", response_model=List[ProduitOut])
def list_deleted_produits(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin]))
):
    return db.query(Produit).filter(Produit.date_suppression.isnot(None)).all()

# 🛆 Scan QR code (vente ou ajout rapide)
@router.post("/scan_qr")
def scan_qr_code(
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock, RoleEnum.technicien, RoleEnum.caissier]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    tracabilite = data.get("tracabilite")
    if not tracabilite:
        raise HTTPException(status_code=400, detail="Tracabilité manquante.")

    produit = db.query(Produit).filter(Produit.tracabilite == tracabilite).first()

    log_action(
            db=db,
            current_user=current_user,
            action="Scan QR produit existant",
            type_entite="produit",
            entite_id=produit.id,
            details=f"Scan de {produit.nom} déclenchant une vente"
        )

    if produit:
        return {
            "action": "vente",
            "produit_id": produit.id,
            "nom": produit.nom,
            "prix_vente": produit.prix_vente,
            "message": "Produit trouvé. Souhaitez-vous lancer une vente ?"
        }
        
        

    else:
        
        log_action(
            db=db,
            current_user=current_user,
            action="Scan QR inconnu",
            type_entite="produit",
            details=f"Scan QR avec tracabilité {tracabilite} — produit non trouvé"
        )

        return {
            "action": "ajout",
            "pre_remplir": {
                "nom": data.get("nom_produit"),
                "tracabilite": tracabilite,
                "societe": data.get("societe")
            },
            "message": "Produit non trouvé. Voulez-vous l'ajouter ?"
        }
        
#Stock d'un produit
@router.get("/{produit_id}/stock-disponible", response_model=dict)
def get_stock_disponible(produit_id: int, db: Session = Depends(get_db)):
    total = db.query(UniteProduit).filter(UniteProduit.produit_id == produit_id).count()
    disponible = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.statut == "disponible"
    ).count()
    en_cours = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.statut == "en_cours"
    ).count()
    return {"stock_total": total, "stock_reel": disponible, "stock_en_attente": en_cours}



