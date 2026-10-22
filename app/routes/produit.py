import json
from fastapi import APIRouter, Depends, HTTPException, Body, File, Form, UploadFile, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import set_committed_value
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
from app.models.model_categorie import Categorie
from app.models.model_fournisseur import Fournisseur
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)
from app.services.traceability_service import create_generated_unit
from app.utils.subscription_guard import (
    enforce_subscription_quota,
    require_subscription_feature,
)
from sqlalchemy import func, or_
import shutil
import os

router = APIRouter(prefix="/produits", tags=["Produits"])


def _with_available_quantities(db: Session, products: list[Produit]):
    """Expose toujours le stock réellement disponible, jamais le stock historique vendu."""
    if not products:
        return products
    product_ids = [product.id for product in products]
    available = dict(
        db.query(UniteProduit.produit_id, func.count(UniteProduit.id))
        .filter(
            UniteProduit.produit_id.in_(product_ids),
            func.lower(UniteProduit.statut) == "disponible",
        )
        .group_by(UniteProduit.produit_id)
        .all()
    )
    for product in products:
        # set_committed_value évite de marquer l'objet comme modifié durant ce GET.
        set_committed_value(product, "quantite", int(available.get(product.id, 0)))
    return products

@router.post("/", response_model=dict)
def create_produit(
    nom: str = Form(...),
    categorie_id: int = Form(...),
    prix_achat: float = Form(0),
    prix_vente: float = Form(0),
    quantite: int = Form(...),
    fournisseur_id: Optional[int] = Form(None),
    rating: Optional[float] = Form(None),
    caracteristiques: Optional[str] = Form(None),
    couleur: Optional[str] = Form(None),
    etat: Optional[str] = Form("oui"),
    commentaire: Optional[str] = Form(None),
    is_installe: Optional[bool] = Form(False),
    emplacement: Optional[str] = Form("magasin"),
    image: Optional[UploadFile] = File(None),
    # scanned_barcodes: Optional[List[str]] = Form(None),
    scanned_barcodes_raw: Optional[str] = Form(None),

    # nombre_unites: Optional[int] = Form(0),  # ✅ nouveau champ pour auto
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    image_path = None

    if not db.query(Categorie.id).filter(
        Categorie.id == categorie_id,
        enterprise_scope_filter(Categorie, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Catégorie non disponible dans cette entreprise")
    if fournisseur_id is not None and not db.query(Fournisseur.id).filter(
        Fournisseur.id == fournisseur_id,
        enterprise_scope_filter(Fournisseur, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Fournisseur non disponible dans cette entreprise")

    enforce_subscription_quota(
        db,
        current_user,
        "max_products",
        db.query(Produit).filter(
            Produit.user_id == parent_user_id,
            Produit.date_suppression.is_(None),
        ).count(),
        "produits",
    )

    try:
        image_url = None
        if image is not None and image.filename:
            original_filename = image.filename
            ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
            if ext not in {"jpg", "jpeg", "png", "webp"}:
                raise HTTPException(status_code=400, detail="Format d'image non pris en charge")
            image_filename = f"{datetime.utcnow().timestamp()}.{ext}"
            upload_dir = os.path.join(os.getcwd(), "upload", "produits")
            os.makedirs(upload_dir, exist_ok=True)
            image_path = os.path.join(upload_dir, image_filename)
            with open(image_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_url = f"/static/produits/{image_filename}"

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
            image_url=image_url,
            user_id=parent_user_id,
            enterprise_id=enterprise_id,
            a_des_barcodes=False
        )

        db.add(produit)
        db.flush()
        db.refresh(produit)
        
        # Parse les codes-barres s'ils existent
        scanned_barcodes = []
        if scanned_barcodes_raw:
            try:
                raw_barcodes = json.loads(scanned_barcodes_raw)
                if not isinstance(raw_barcodes, list):
                    raise ValueError("Une liste est requise")
                scanned_barcodes = list(dict.fromkeys(
                    code.strip()
                    for code in raw_barcodes
                    if isinstance(code, str) and code.strip()
                ))
            except (TypeError, ValueError, json.JSONDecodeError):
                raise HTTPException(status_code=400, detail="Format JSON invalide pour scanned_barcodes")


        # 🔍 Gestion des unités : SCAN manuel
        if scanned_barcodes and len(scanned_barcodes) > 0:
            unites = []
            conflicts = []
            now = datetime.utcnow()
            for code in scanned_barcodes:
                exists = db.query(UniteProduit).filter(
                    UniteProduit.enterprise_id == enterprise_id,
                    or_(
                        UniteProduit.code_barre == code,
                        UniteProduit.tracabilite == code,
                    )
                ).first()
                if exists:
                    # Les codes validés par le scanner sont d'abord placés en
                    # attente. La création de la fiche doit les rattacher ici,
                    # dans la même transaction, au lieu d'imposer un 2e appel.
                    if exists.produit_id is None:
                        exists.produit_id = produit.id
                        exists.statut = "disponible"
                        exists.date_creation = now
                        exists.date_modification = now
                        unites.append(exists)
                        continue
                    conflicts.append(code)
                    continue

                unites.append(UniteProduit(
                    produit_id=produit.id,
                    enterprise_id=enterprise_id,
                    tracabilite=code,
                    code_barre=code,
                    statut="disponible",
                    date_creation=now,
                ))

            if conflicts:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Certains codes-barres appartiennent déjà à une autre fiche : "
                        + ", ".join(conflicts[:5])
                    ),
                )

            if unites:
                db.add_all(unites)
                produit.a_des_barcodes = True
                
                # ✅ AJOUTE CETTE LIGNE ICI
                produit.quantite = len(unites)
                
                db.flush()
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
            for _ in range(quantite):
                create_generated_unit(
                    db,
                    produit_id=produit.id,
                    enterprise_id=enterprise_id,
                )

            db.flush()

            log_action(
                db=db,
                current_user=current_user,
                action="Ajout produit avec QR auto",
                type_entite="produit",
                entite_id=produit.id,
                details=f"{quantite} unités générées avec QR pour produit {produit.nom}"
            )

        db.commit()
        return {"message": "Produit créé avec succès", "produit_id": produit.id}

    except HTTPException:
        db.rollback()
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        raise
    except Exception as e:
        db.rollback()
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        print("❌ ERREUR lors de la création du produit :", str(e))
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du produit")




# 📋 Lister tous les produits actifs
@router.get("/", response_model=List[ProduitOut])
def list_produits(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1, max_length=120),
    categorie_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user=Depends(All_required())
):
    query = db.query(Produit).options(joinedload(Produit.categorie)).filter(
        Produit.date_suppression == None,
        enterprise_scope_filter(Produit, current_user),
    )
    if search:
        query = query.filter(Produit.nom.ilike(f"%{search.strip()}%"))
    if categorie_id is not None:
        query = query.filter(Produit.categorie_id == categorie_id)
    products = (
        query.order_by(Produit.date_creation.desc(), Produit.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return _with_available_quantities(db, products)


@router.get("/stats/count", response_model=dict)
def product_count_stats(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    articles, quantity = db.query(
        func.count(Produit.id),
        func.coalesce(func.sum(Produit.quantite), 0),
    ).filter(
        Produit.date_suppression.is_(None),
        enterprise_scope_filter(Produit, current_user),
    ).one()
    ruptures = db.query(func.count(Produit.id)).filter(
        Produit.date_suppression.is_(None),
        Produit.quantite <= 0,
        enterprise_scope_filter(Produit, current_user),
    ).scalar()
    return {
        "articles": int(articles or 0),
        "quantite_totale": int(quantity or 0),
        "ruptures": int(ruptures or 0),
    }


@router.get("/characteristics/suggestions", response_model=List[str])
def product_characteristic_suggestions(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    """Retourne les caractéristiques réutilisables, les plus complètes d'abord."""
    rows = (
        db.query(
            Produit.caracteristiques,
            func.length(Produit.caracteristiques).label("text_length"),
        )
        .filter(
            Produit.date_suppression.is_(None),
            Produit.caracteristiques.isnot(None),
            func.length(func.trim(Produit.caracteristiques)) > 0,
            enterprise_scope_filter(Produit, current_user),
        )
        .group_by(Produit.caracteristiques)
        .order_by(func.length(Produit.caracteristiques).desc())
        .limit(limit)
        .all()
    )
    return [value.strip() for value, _ in rows if value and value.strip()]

# 🔍 Voir un produit par ID
@router.get("/{produit_id}", response_model=ProduitOut)
def get_produit(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        Produit.date_suppression == None,
        enterprise_scope_filter(Produit, current_user),
    ).first()

    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    return _with_available_quantities(db, [produit])[0]



# 🔄 Modifier un produit
@router.put("/{produit_id}/", response_model=dict)
def update_produit(
    produit_id: int,
    nom: str = Form(...),
    categorie_id: int = Form(...),
    prix_achat: float = Form(0),
    prix_vente: float = Form(0),
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
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
        Produit.date_suppression.is_(None),
    ).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    if not db.query(Categorie.id).filter(
        Categorie.id == categorie_id,
        enterprise_scope_filter(Categorie, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Catégorie non disponible dans cette entreprise")
    if fournisseur_id is not None and not db.query(Fournisseur.id).filter(
        Fournisseur.id == fournisseur_id,
        enterprise_scope_filter(Fournisseur, current_user),
    ).first():
        raise HTTPException(status_code=400, detail="Fournisseur non disponible dans cette entreprise")

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
            normalized_barcodes = list(dict.fromkeys(
                code.strip() for code in barcodes
                if isinstance(code, str) and code.strip()
            ))
            for code in normalized_barcodes:
                exists = db.query(UniteProduit).filter(
                    UniteProduit.code_barre == code,
                    UniteProduit.enterprise_id == enterprise_id,
                ).first()
                if not exists:
                    new_unite = UniteProduit(
                        produit_id=produit.id,
                        enterprise_id=enterprise_id,
                        tracabilite=code,
                        code_barre=code,
                        statut="disponible",
                        date_creation=datetime.utcnow(),
                    )
                    db.add(new_unite)
                    new_count += 1

            if new_count > 0:
                produit.a_des_barcodes = True
                db.flush()
                produit.quantite = db.query(UniteProduit).filter(
                    UniteProduit.produit_id == produit.id,
                    UniteProduit.statut == "disponible",
                ).count()

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
    parent_user_id = actor_owner_id(current_user)

    produit = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
    ).first()
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
    return db.query(Produit).filter(
        Produit.date_suppression.isnot(None),
        enterprise_scope_filter(Produit, current_user),
    ).all()

# 🛆 Scan QR code (vente ou ajout rapide)
@router.post(
    "/scan_qr",
    dependencies=[Depends(require_subscription_feature("basic_qr"))],
)
def scan_qr_code(
    data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock, RoleEnum.technicien, RoleEnum.caissier]))
):
    parent_user_id = actor_owner_id(current_user)
    tracabilite = data.get("tracabilite")
    if not tracabilite:
        raise HTTPException(status_code=400, detail="Tracabilité manquante.")

    unite = db.query(UniteProduit).join(UniteProduit.produit).filter(
        UniteProduit.tracabilite == tracabilite,
        enterprise_scope_filter(Produit, current_user),
    ).first()
    produit = unite.produit if unite else None

    if produit:
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
def get_stock_disponible(
    produit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    product_exists = db.query(Produit.id).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
    ).first()
    if not product_exists:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    total = db.query(UniteProduit).filter(UniteProduit.produit_id == produit_id).count()
    disponible = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.statut == "disponible"
    ).count()
    en_cours = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        func.lower(UniteProduit.statut).in_(["en_cours", "en cours"])
    ).count()
    return {"stock_total": total, "stock_reel": disponible, "stock_en_attente": en_cours}



