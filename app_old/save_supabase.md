from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.model_galerie import GaleriePhoto
from app.models.model_produit import Produit
from typing import List
from app.schemas.galerie_schema import GalerieOut
from app.services.supabase_service import upload_to_supabase, delete_from_supabase
from uuid import uuid4
from datetime import datetime

router = APIRouter(prefix="/galerie", tags=["Galerie Produit"])

@router.post("/", response_model=dict)
def ajouter_photo_galerie(
    produit_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    file_url = upload_to_supabase(file=file, bucket="galerie", filename=filename)

    g = GaleriePhoto(
        produit_id=produit_id,
        image_url=file_url,
        date_ajout=datetime.utcnow()
    )
    db.add(g)
    db.commit()
    db.refresh(g)

    return {"message": "Image ajoutée à la galerie", "image_url": g.image_url}


@router.put("/{image_id}", response_model=dict)
def update_image_galerie(
    image_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    image = db.query(GaleriePhoto).filter(GaleriePhoto.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image non trouvée")

    # Supprimer ancienne image dans Supabase
    if image.image_url:
        delete_from_supabase(image.image_url)

    # Enregistrer la nouvelle image
    ext = file.filename.split(".")[-1]
    filename = f"{uuid4()}.{ext}"
    file_url = upload_to_supabase(file=file, bucket="galerie", filename=filename)

    image.image_url = file_url
    db.commit()
    db.refresh(image)

    return {"message": "Image mise à jour avec succès", "image_url": image.image_url}


@router.delete("/{image_id}", response_model=dict)
def delete_image_galerie(image_id: int, db: Session = Depends(get_db)):
    image = db.query(GaleriePhoto).filter(GaleriePhoto.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image non trouvée")

    if image.image_url:
        delete_from_supabase(image.image_url)

    db.delete(image)
    db.commit()

    return {"message": "Image supprimée avec succès"}


@router.get("/{produit_id}", response_model=List[GalerieOut])
def get_galerie_by_produit(produit_id: int, db: Session = Depends(get_db)):
    images = db.query(GaleriePhoto).filter(GaleriePhoto.produit_id == produit_id).order_by(GaleriePhoto.date_ajout.desc()).all()
    return images
**********************************************profil****************

from fastapi import File, HTTPException, UploadFile, Depends, APIRouter
from sqlalchemy.orm import Session
from uuid import uuid4
from app.database import get_db
from app.models.model_user import User, SubUser
from app.utils.security import get_current_user, get_current_sub_user
from app.utils.logger import log_action
from app.services.supabase_service import upload_to_supabase, delete_from_supabase

router = APIRouter(prefix="/upload", tags=["Fichiers"])

# 📄 Upload avatar utilisateur principal
@router.post("/avatar-user")
def upload_avatar_for_user(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = f"{uuid4()}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="avatars", filename=filename)

    current_user.avatar_url = file_url
    db.commit()
    db.refresh(current_user)

    log_action(
        db=db,
        current_user=current_user,
        action="Upload avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal mis à jour"
    )

    return {"avatar_url": file_url, "message": "Avatar uploaded and linked successfully."}


# 📄 Upload avatar sub-user
@router.post("/avatar-sub")
def upload_avatar_for_subuser(
    file: UploadFile = File(...),
    current_sub: SubUser = Depends(get_current_sub_user),
    db: Session = Depends(get_db)
):
    filename = f"{uuid4()}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="avatars", filename=filename)

    current_sub.avatar_url = file_url
    db.commit()
    db.refresh(current_sub)

    log_action(
        db=db,
        current_user=current_sub,
        action="Upload avatar",
        type_entite="sub-user",
        entite_id=current_sub.id,
        details="Avatar sub-user mis à jour"
    )

    return {"avatar_url": file_url, "message": "Avatar uploaded and linked successfully."}


# 👤 Get avatar utilisateur principal
@router.get("/avatar-user")
def get_avatar_user(current_user: User = Depends(get_current_user)):
    return {"avatar_url": current_user.avatar_url}


# 👤 Get avatar sub-user
@router.get("/avatar-sub")
def get_avatar_subuser(current_sub: SubUser = Depends(get_current_sub_user)):
    return {"avatar_url": current_sub.avatar_url}


# 🧽 Delete avatar utilisateur principal
@router.delete("/delete/avatar")
def delete_avatar_file(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.avatar_url:
        raise HTTPException(status_code=404, detail="Aucun avatar défini.")

    delete_from_supabase(current_user.avatar_url)
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression avatar",
        type_entite="utilisateur",
        entite_id=current_user.id,
        details="Avatar utilisateur principal supprimé"
    )

    return {"message": "Avatar supprimé avec succès."}


# ****************** LOGO ********************
@router.post("/logo")
def upload_logo_entreprise(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    filename = f"logo_{current_user.id}.{file.filename.split('.')[-1]}"
    file_url = upload_to_supabase(file=file, bucket="logo", filename=filename)

    current_user.logo_entreprise = file_url
    db.commit()
    db.refresh(current_user)

    return {"logo_url": file_url}


@router.get("/logo")
def get_logo_entreprise(current_user: User = Depends(get_current_user)):
    if not current_user.logo_entreprise:
        raise HTTPException(status_code=404, detail="Aucun logo enregistré")
    return {"logo_url": current_user.logo_entreprise}


@router.delete("/delete/logo")
def delete_logo_entreprise(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):

    if not current_user.logo_entreprise:
        raise HTTPException(status_code=404, detail="Aucun logo défini")

    delete_from_supabase(current_user.logo_entreprise)
    current_user.logo_entreprise = None
    db.commit()
    db.refresh(current_user)

    return {"message": "Logo supprimé"}
*****************************************************************

from fastapi import APIRouter, Depends, HTTPException, Body, File, Form, UploadFile 
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.model_produit import Produit
from app.schemas.produit_schema import ProduitCreate, ProduitOut
from pydantic import BaseModel
from datetime import datetime
from app.utils.logger import log_action
from app.utils.permissions import check_role
from app.utils.security import get_current_user
from app.models.model_user import User
from app.schemas.user_schema import RoleEnum
from app.models.model_unite_produit import UniteProduit
from app.services.supabase_service import upload_to_supabase, delete_from_supabase
from uuid import uuid4

router = APIRouter(prefix="/produits", tags=["Produits"])

# ➕ Créer un produit avec image (multipart)
@router.post("/", response_model=dict)
def create_produit(
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
    tracabilite: Optional[str] = Form(None),
    emplacement: Optional[str] = Form("magasin"),
    image: UploadFile = File(...),
    scanned_barcodes: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    ext = image.filename.split(".")[-1]
    image_filename = f"{uuid4()}.{ext}"
    image_url = upload_to_supabase(file=image, bucket="produits", filename=image_filename)

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
        tracabilite=tracabilite,
        emplacement=emplacement,
        image_url=image_url,
        user_id=parent_user_id
    )

    db.add(produit)
    db.commit()
    db.refresh(produit)

    if scanned_barcodes:
        for code in scanned_barcodes:
            unite = UniteProduit(
                produit_id=produit.id,
                code_barre=code,
                statut="disponible"
            )
            db.add(unite)
    else:
        for i in range(1, quantite + 1):
            qr_code = f"TRAC-{produit.id}-{str(i).zfill(4)}"
            unite = UniteProduit(
                produit_id=produit.id,
                tracabilite=qr_code,
                statut="disponible"
            )
            db.add(unite)

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Ajout produit avec unités",
        type_entite="produit",
        entite_id=produit.id,
        details=f"{quantite} unités créées avec QR pour produit {produit.nom}"
    )

    return {"message": "Produit créé avec succès", "produit_id": produit.id}


# 📋 Lister tous les produits actifs
@router.get("/", response_model=List[ProduitOut])
def list_produits(
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
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
    produit = db.query(Produit).filter(Produit.id == produit_id, Produit.date_suppression == None).first()
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
    tracabilite: Optional[str] = Form(None),
    emplacement: Optional[str] = Form("magasin"),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user=Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):

    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    if image:
        if produit.image_url:
            delete_from_supabase(produit.image_url)

        ext = image.filename.split(".")[-1]
        image_filename = f"{uuid4()}.{ext}"
        image_url = upload_to_supabase(file=image, bucket="produits", filename=image_filename)
        produit.image_url = image_url

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
    produit.tracabilite = tracabilite
    produit.emplacement = emplacement
    produit.date_modification = datetime.utcnow()

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
    produit.date_suppression = datetime.utcnow()
    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Suppression Produit",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit {produit.nom} supprimé logiquement"
    )

    return {"message": "Produit supprimé (logiquement)"}

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
