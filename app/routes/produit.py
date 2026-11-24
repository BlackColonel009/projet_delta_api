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
from uuid import uuid4
import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape
from fastapi.responses import StreamingResponse
from app.utils.logger import log_action
from app.utils.permissions import All_required, check_role
from app.utils.security import get_current_user
from app.models.model_user import User
from app.schemas.user_schema import RoleEnum
from app.models.model_unite_produit import UniteProduit
from app.models.model_categorie import Categorie
from app.models.model_fournisseur import Fournisseur
from app.models.model_galerie import GaleriePhoto
from app.models.model_client import Client
from app.models.model_commande import CommandeVente, LigneCommandeVente
from app.services.enterprise_service import (
    actor_enterprise_id,
    actor_owner_id,
    enterprise_scope_filter,
)
from app.services.traceability_service import create_generated_unit
from app.services.unit_reassignment_service import (
    attach_reusable_unit,
    count_available_units,
    product_has_tracked_units,
    refresh_available_product_quantity,
)
from app.utils.subscription_guard import (
    enforce_subscription_quota,
    require_subscription_feature,
)
from sqlalchemy import and_, case, func, or_
from reportlab.lib import colors as pdf_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
import shutil
import os

router = APIRouter(prefix="/produits", tags=["Produits"])


def _product_search_variants(value: str) -> tuple[str, str, list[str], str]:
    """Normalize loose spacing/case and build conservative acronym variants."""
    ascii_value = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in ascii_value if not unicodedata.combining(char))
    ascii_value = ascii_value.lower()
    tokens = re.findall(r"[a-z]+|[0-9]+", ascii_value)
    compact = "".join(tokens)
    if not tokens:
        return "", "", [], ""
    # `Core 5`, `core5`, and `C5` all produce the compact alias `c5`.
    initials = "".join(token if token.isdigit() else token[0] for token in tokens)
    separator = r"[[:space:][:punct:]]*"
    flexible_pattern = r"(^|[^[:alnum:]])" + separator.join(
        re.escape(token) for token in tokens
    ) + r"([^[:alnum:]]|$)"
    return compact, initials, [flexible_pattern], ascii_value


def _unaccented_sql_text(column):
    return func.translate(
        func.lower(func.coalesce(column, "")),
        "áàâäãåéèêëíìîïóòôöõúùûüçñýÿ",
        "aaaaaaeeeeiiiiooooouuuucnyy",
    )


def _normalized_sql_text(column):
    return func.regexp_replace(
        _unaccented_sql_text(column), r"[^a-z0-9]+", "", "g"
    )


def _initials_sql_text(column):
    words_initials = func.regexp_replace(
        _unaccented_sql_text(column), r"([a-z])[a-z]*", r"\1", "g"
    )
    return func.regexp_replace(words_initials, r"[^a-z0-9]+", "", "g")


def _initials_match(column, initials: str):
    # Permit trailing words (Core 5 Phone for query C5), but not a different
    # number (Core 50 must not match Core 5).
    return _initials_sql_text(column).op("~*")(
        r"^" + re.escape(initials) + r"([a-z]|$)"
    )


def _with_available_quantities(db: Session, products: list[Produit]):
    """Expose le vrai stock : unités disponibles pour le stock tracé, compteur sinon."""
    if not products:
        return products
    product_ids = [product.id for product in products]
    unit_stats = db.query(
        UniteProduit.produit_id,
        func.count(UniteProduit.id),
        func.sum(
            case(
                (
                    func.lower(func.trim(func.coalesce(UniteProduit.statut, "")))
                    == "disponible",
                    1,
                ),
                else_=0,
            )
        ),
    ).join(
        Produit, Produit.id == UniteProduit.produit_id
    ).filter(
        Produit.id.in_(product_ids),
        or_(
            UniteProduit.enterprise_id == Produit.enterprise_id,
            and_(
                UniteProduit.enterprise_id.is_(None),
                Produit.enterprise_id.is_(None),
            ),
        ),
    ).group_by(UniteProduit.produit_id).all()
    tracked_ids = {row[0] for row in unit_stats if row[1] > 0}
    available = {row[0]: int(row[2] or 0) for row in unit_stats}

    for product in products:
        if product.a_des_barcodes or product.id in tracked_ids:
            # set_committed_value empêche un GET de modifier l'objet ORM.
            set_committed_value(product, "quantite", available.get(product.id, 0))
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
    clone_source_product_id: Optional[int] = Form(None),

    # nombre_unites: Optional[int] = Form(0),  # ✅ nouveau champ pour auto
    db: Session = Depends(get_db),
    current_user = Depends(check_role([RoleEnum.admin, RoleEnum.gestionnaire_stock]))
):
    parent_user_id = actor_owner_id(current_user)
    enterprise_id = actor_enterprise_id(current_user)
    image_path = None
    cloned_gallery_paths: list[str] = []

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
        elif clone_source_product_id is not None:
            source_product = db.query(Produit).filter(
                Produit.id == clone_source_product_id,
                Produit.date_suppression.is_(None),
                enterprise_scope_filter(Produit, current_user),
            ).first()
            if not source_product:
                raise HTTPException(
                    status_code=404,
                    detail="La fiche produit à cloner est introuvable.",
                )
            if source_product.image_url:
                relative_source = source_product.image_url.split("/static/", 1)
                if len(relative_source) == 2:
                    source_path = os.path.join(
                        os.getcwd(),
                        "upload",
                        relative_source[1].replace("/", os.sep),
                    )
                    if os.path.isfile(source_path):
                        extension = os.path.splitext(source_path)[1] or ".jpg"
                        image_filename = f"{uuid4().hex}{extension.lower()}"
                        upload_dir = os.path.join(os.getcwd(), "upload", "produits")
                        os.makedirs(upload_dir, exist_ok=True)
                        image_path = os.path.join(upload_dir, image_filename)
                        shutil.copy2(source_path, image_path)
                        image_url = f"/static/produits/{image_filename}"

        # 🧱 Création du produit (sans champ quantite ni tracabilite)
        produit = Produit(
            nom=nom,
            categorie_id=categorie_id,
            prix_achat=prix_achat,
            prix_vente=prix_vente,
            fournisseur_id=fournisseur_id,
            # Une fiche clonée est toujours créée sans unité. La valeur du
            # client est ignorée pour garantir le stock initial à zéro.
            quantite=0 if clone_source_product_id is not None else quantite,
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
        if clone_source_product_id is not None:
            scanned_barcodes = []

        if scanned_barcodes and len(scanned_barcodes) > 0:
            unites = []
            conflicts = []
            moved_units = []
            previous_product_ids = set()
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
                    attachment = attach_reusable_unit(
                        exists,
                        produit,
                        enterprise_id=enterprise_id,
                        now=now,
                    )
                    if attachment.was_added:
                        if attachment.previous_product_id not in (None, produit.id):
                            previous_product_ids.add(attachment.previous_product_id)
                            moved_units.append(code)
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
                db.flush()
                produit.quantite = count_available_units(db, produit.id, enterprise_id)
                for previous_product_id in previous_product_ids:
                    refresh_available_product_quantity(db, previous_product_id)
                
                db.refresh(produit)

                log_action(
                    db=db,
                    current_user=current_user,
                    action="Ajout produit avec codes-barres",
                    type_entite="produit",
                    entite_id=produit.id,
                    details=(
                        f"{len(unites)} unités scannées ajoutées au produit {produit.nom}. "
                        f"{len(moved_units)} unité(s) indisponible(s) réaffectée(s)."
                    )
                )

        # ⚙️ Sinon : génération automatique par nombre
        elif clone_source_product_id is None and quantite > 0:
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

        if clone_source_product_id is not None:
            for source_photo in source_product.galerie:
                relative_gallery = source_photo.image_url.split("/static/", 1)
                if len(relative_gallery) != 2:
                    continue
                gallery_source_path = os.path.join(
                    os.getcwd(),
                    "upload",
                    relative_gallery[1].replace("/", os.sep),
                )
                if not os.path.isfile(gallery_source_path):
                    continue
                gallery_extension = (
                    os.path.splitext(gallery_source_path)[1] or ".jpg"
                )
                gallery_filename = f"{uuid4().hex}{gallery_extension.lower()}"
                gallery_directory = os.path.join(os.getcwd(), "upload", "galerie")
                os.makedirs(gallery_directory, exist_ok=True)
                shutil.copy2(
                    gallery_source_path,
                    os.path.join(gallery_directory, gallery_filename),
                )
                cloned_gallery_paths.append(
                    os.path.join(gallery_directory, gallery_filename)
                )
                db.add(
                    GaleriePhoto(
                        produit_id=produit.id,
                        enterprise_id=enterprise_id,
                        image_url=f"/static/galerie/{gallery_filename}",
                        date_ajout=datetime.utcnow(),
                    )
                )

            log_action(
                db=db,
                current_user=current_user,
                action="Clonage d'une fiche produit",
                type_entite="produit",
                entite_id=produit.id,
                details=(
                    f"Fiche {source_product.nom} clonée vers {produit.nom} "
                    "sans unité et avec un stock initial nul."
                ),
            )

        db.commit()
        return {"message": "Produit créé avec succès", "produit_id": produit.id}

    except HTTPException:
        db.rollback()
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        for cloned_path in cloned_gallery_paths:
            if os.path.exists(cloned_path):
                os.remove(cloned_path)
        raise
    except Exception as e:
        db.rollback()
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        for cloned_path in cloned_gallery_paths:
            if os.path.exists(cloned_path):
                os.remove(cloned_path)
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
        compact_search, acronym_search, patterns, _normalized_search = (
            _product_search_variants(search.strip())
        )
        if not compact_search:
            raise HTTPException(status_code=422, detail="Recherche invalide")
        enterprise_id = actor_enterprise_id(current_user)
        query = query.outerjoin(
            Categorie,
            Produit.categorie_id == Categorie.id,
        )
        text_fields = (
            Produit.nom,
            Categorie.nom,
            Produit.caracteristiques,
            Produit.couleur,
            Produit.commentaire,
            Produit.emplacement,
        )
        flexible_matches = [
            _unaccented_sql_text(field).op("~*")(pattern)
            for field in text_fields
            for pattern in patterns
        ]
        code_matches = [
            _unaccented_sql_text(code_field).op("~*")(pattern)
            for code_field in (UniteProduit.tracabilite, UniteProduit.code_barre)
            for pattern in patterns
        ]
        code_matches.extend(
            code_field.ilike(f"%{search.strip()}%")
            for code_field in (UniteProduit.tracabilite, UniteProduit.code_barre)
        )
        allow_acronym = len(re.findall(r"[a-z]+|[0-9]+", _normalized_search)) > 1
        if acronym_search and allow_acronym:
            flexible_matches.extend(
                _initials_match(field, acronym_search)
                for field in text_fields
            )
            code_matches.extend(
                _initials_match(code_field, acronym_search)
                for code_field in (UniteProduit.tracabilite, UniteProduit.code_barre)
            )
        query = query.filter(
            or_(
                *flexible_matches,
                Produit.unites.any(
                    (UniteProduit.enterprise_id == enterprise_id)
                    & or_(*code_matches)
                ),
            )
        )
        available_count = (
            db.query(func.count(UniteProduit.id))
            .filter(
                UniteProduit.produit_id == Produit.id,
                func.lower(UniteProduit.statut) == "disponible",
            )
            .correlate(Produit)
            .scalar_subquery()
        )
        name_matches = or_(
            *(
                _unaccented_sql_text(Produit.nom).op("~*")(pattern)
                for pattern in patterns
            )
        )
        if acronym_search and allow_acronym:
            name_matches = or_(
                name_matches,
                _initials_match(Produit.nom, acronym_search),
            )
        relevance = case(
            (_normalized_sql_text(Produit.nom) == compact_search, 0),
            (name_matches, 1),
            (or_(*flexible_matches), 2),
            else_=3,
        )
        query = query.order_by(
            case((available_count > 0, 0), else_=1),
            relevance.asc(),
            Produit.date_creation.desc(),
            Produit.id.desc(),
        )
    if categorie_id is not None:
        query = query.filter(Produit.categorie_id == categorie_id)
    if not search:
        query = query.order_by(Produit.date_creation.desc(), Produit.id.desc())
    products = query.offset(offset).limit(limit).all()
    return _with_available_quantities(db, products)


@router.post("/reports/selection.pdf", response_class=StreamingResponse)
def export_selected_products_report(
    product_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    selected_ids = list(dict.fromkeys(product_ids))
    if not selected_ids or len(selected_ids) > 200:
        raise HTTPException(
            status_code=422,
            detail="Sélectionnez entre 1 et 200 produits pour le rapport.",
        )

    products = db.query(Produit).options(joinedload(Produit.categorie)).filter(
        Produit.id.in_(selected_ids),
        Produit.date_suppression.is_(None),
        enterprise_scope_filter(Produit, current_user),
    ).all()
    if len(products) != len(selected_ids):
        # Ne révèle pas si un identifiant existe dans une autre entreprise.
        raise HTTPException(status_code=404, detail="Un ou plusieurs produits sont introuvables.")

    units = db.query(UniteProduit).filter(
        UniteProduit.produit_id.in_(selected_ids),
    ).order_by(UniteProduit.produit_id, UniteProduit.id).all()
    units_by_product: dict[int, list[UniteProduit]] = {}
    for unit in units:
        units_by_product.setdefault(unit.produit_id, []).append(unit)

    sales = db.query(LigneCommandeVente, CommandeVente, Client).join(
        CommandeVente,
        LigneCommandeVente.commande_id == CommandeVente.id,
    ).join(
        Client,
        CommandeVente.client_id == Client.id,
    ).filter(
        LigneCommandeVente.produit_id.in_(selected_ids),
        CommandeVente.statut.in_(["validée", "en_attente"]),
        enterprise_scope_filter(LigneCommandeVente, current_user),
        enterprise_scope_filter(CommandeVente, current_user),
        enterprise_scope_filter(Client, current_user),
    ).order_by(
        CommandeVente.date_commande.desc(),
        CommandeVente.id.desc(),
        LigneCommandeVente.id.desc(),
    ).all()
    sales_by_product: dict[int, list[tuple[LigneCommandeVente, CommandeVente, Client]]] = {}
    for line, order, client in sales:
        sales_by_product.setdefault(line.produit_id, []).append((line, order, client))

    order_ids = list({order.id for _, order, _ in sales})
    units_by_sale: dict[tuple[int, int], list[UniteProduit]] = {}
    if order_ids:
        sale_units = db.query(UniteProduit).join(
            Produit,
            UniteProduit.produit_id == Produit.id,
        ).filter(
            UniteProduit.commande_vente_id.in_(order_ids),
            UniteProduit.produit_id.in_(selected_ids),
            enterprise_scope_filter(Produit, current_user),
        ).order_by(UniteProduit.commande_vente_id, UniteProduit.id).all()
        for unit in sale_units:
            key = (unit.commande_vente_id, unit.produit_id)
            units_by_sale.setdefault(key, []).append(unit)

    products_by_id = {product.id: product for product in products}
    ordered_products = [products_by_id[product_id] for product_id in selected_ids]

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title="Rapport personnalisé des produits",
        author="Trade Care",
    )
    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TradeCareProductReportTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=pdf_colors.HexColor("#123B5D"),
        alignment=0,
        spaceAfter=5,
    )
    subtitle_style = ParagraphStyle(
        "TradeCareProductReportSubtitle",
        parent=base_styles["Normal"],
        fontSize=9,
        textColor=pdf_colors.HexColor("#5A6B78"),
        spaceAfter=14,
    )
    product_style = ParagraphStyle(
        "TradeCareProductName",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=pdf_colors.HexColor("#123B5D"),
        spaceBefore=5,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "TradeCareProductBody",
        parent=base_styles["BodyText"],
        fontSize=8.5,
        leading=12,
        spaceAfter=5,
        splitLongWords=1,
    )
    small_style = ParagraphStyle(
        "TradeCareProductSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
        textColor=pdf_colors.HexColor("#354A59"),
    )
    section_style = ParagraphStyle(
        "TradeCareProductReportSection",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=pdf_colors.HexColor("#123B5D"),
        spaceAfter=8,
    )

    story = [
        Paragraph("Rapport personnalisé des produits", title_style),
        Paragraph(
            f"{len(ordered_products)} produit(s) sélectionné(s) · "
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            subtitle_style,
        ),
        Paragraph(
            "Stock de départ connu = nombre d’unités encore rattachées à la fiche, "
            "tous statuts confondus. Les suppressions définitives antérieures ne "
            "peuvent pas être reconstituées.",
            small_style,
        ),
        Spacer(1, 8),
    ]
    company_name = getattr(current_user, "societe_ou_entreprise", None)
    if company_name:
        story.insert(1, Paragraph(escape(str(company_name)), subtitle_style))

    for index, product in enumerate(ordered_products, start=1):
        product_units = units_by_product.get(product.id, [])
        available = sum(
            1 for unit in product_units
            if (unit.statut or "").strip().lower() == "disponible"
        )
        pending = sum(
            1 for unit in product_units
            if (unit.statut or "").strip().lower()
            in {"en_cours", "en cours", "en_attente", "en attente"}
        )
        sold = sum(
            1 for unit in product_units
            if (unit.statut or "").strip().lower() == "vendu"
        )
        other = max(0, len(product_units) - available - pending - sold)
        category = getattr(product.categorie, "nom", None)
        story.append(Paragraph(f"{index}. {escape(product.nom or 'Produit sans nom')}", product_style))
        stats = Table(
            [["CATÉGORIE", "STOCK DÉPART*", "DISPONIBLE", "EN ATTENTE", "VENDU", "AUTRES"],
             [escape(str(category or "—")), str(len(product_units)), str(available),
              str(pending), str(sold), str(other)]],
            colWidths=[4.3 * cm, 2.7 * cm, 2.5 * cm, 2.7 * cm, 2.2 * cm, 2.6 * cm],
            repeatRows=1,
        )
        stats.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), pdf_colors.HexColor("#EAF1F5")),
            ("TEXTCOLOR", (0, 0), (-1, 0), pdf_colors.HexColor("#123B5D")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, pdf_colors.HexColor("#D7E1E7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([stats, Spacer(1, 7)])

        characteristics = (product.caracteristiques or "").strip()
        if characteristics:
            formatted_characteristics = escape(characteristics).replace("\n", "<br/>")
            story.append(Paragraph(
                f"<b>Caractéristiques :</b> {formatted_characteristics}", body_style
            ))
        if product.couleur:
            story.append(Paragraph(
                f"<b>Couleur :</b> {escape(product.couleur)}", body_style
            ))

        code_entries = []
        for unit in product_units:
            code_values = list(dict.fromkeys(
                value.strip()
                for value in (unit.code_barre, unit.tracabilite)
                if value and value.strip()
            ))
            if code_values:
                status = (unit.statut or "statut inconnu").replace("_", " ")
                code_entries.append(f"{', '.join(code_values)} [{status}]")
        story.append(Paragraph("<b>Codes-barres / traçabilités liés :</b>", body_style))
        if code_entries:
            for start in range(0, len(code_entries), 8):
                chunk = "<br/>".join(escape(value) for value in code_entries[start:start + 8])
                story.append(Paragraph(chunk, small_style))
        else:
            story.append(Paragraph("Aucun code lié.", small_style))
        if index < len(ordered_products):
            story.append(Spacer(1, 10))

    story.extend([
        PageBreak(),
        Paragraph("Achats clients des produits sélectionnés", section_style),
        Paragraph(
            "Historique des ventes validées ou en attente, avec les codes rattachés "
            "à chaque commande lorsqu’ils sont enregistrés.",
            subtitle_style,
        ),
    ])
    has_sales = False
    for product in ordered_products:
        product_sales = sales_by_product.get(product.id, [])
        story.append(Paragraph(escape(product.nom or "Produit sans nom"), product_style))
        if not product_sales:
            story.append(Paragraph("Aucun achat client enregistré pour ce produit.", body_style))
            story.append(Spacer(1, 8))
            continue

        has_sales = True
        product_has_codes = any(
            unit.code_barre or unit.tracabilite
            for unit in units_by_product.get(product.id, [])
        )
        for line, order, client in product_sales:
            date_label = (
                order.date_commande.strftime("%d/%m/%Y")
                if order.date_commande
                else "—"
            )
            metadata = Table(
                [[
                    Paragraph(f"<b>Client</b><br/>{escape(client.nom or 'Client sans nom')}", small_style),
                    Paragraph(f"<b>Date</b><br/>{date_label}", small_style),
                    Paragraph(f"<b>Quantité</b><br/>{line.quantite}", small_style),
                    Paragraph(f"<b>Statut</b><br/>{escape(order.statut or '—')}", small_style),
                ]],
                colWidths=[6.2 * cm, 2.8 * cm, 2.5 * cm, 4.8 * cm],
            )
            metadata.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), pdf_colors.HexColor("#F4F7F9")),
                ("GRID", (0, 0), (-1, -1), 0.35, pdf_colors.HexColor("#D7E1E7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.extend([metadata, Spacer(1, 3)])

            linked_units = units_by_sale.get((order.id, product.id), [])
            linked_codes = []
            for unit in linked_units:
                linked_codes.extend(
                    value.strip()
                    for value in (unit.code_barre, unit.tracabilite)
                    if value and value.strip()
                )
            linked_codes = list(dict.fromkeys(linked_codes))
            if linked_codes:
                story.append(Paragraph("<b>Codes liés à cette vente :</b>", small_style))
                for start in range(0, len(linked_codes), 8):
                    chunk = " · ".join(
                        escape(code) for code in linked_codes[start:start + 8]
                    )
                    story.append(Paragraph(chunk, small_style))
            elif product_has_codes:
                story.append(Paragraph(
                    "Des codes existent sur la fiche, mais aucun n’est rattaché "
                    "à cette vente.",
                    small_style,
                ))
            else:
                story.append(Paragraph("Aucun code enregistré pour ce produit.", small_style))
            story.append(Spacer(1, 8))

    if not has_sales:
        story.append(Paragraph(
            "Aucun achat client n’a été enregistré pour les produits sélectionnés.",
            body_style,
        ))

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(pdf_colors.HexColor("#D7E1E7"))
        canvas.line(1.6 * cm, 1.25 * cm, A4[0] - 1.6 * cm, 1.25 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(pdf_colors.HexColor("#647784"))
        canvas.drawString(1.6 * cm, 0.85 * cm, "Trade Care · Rapport produits et achats")
        canvas.drawRightString(A4[0] - 1.6 * cm, 0.85 * cm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    filename = f"rapport_produits_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    # La quantité du formulaire reste la source pour les produits non suivis
    # par unité. Pour un produit QR/code-barres, elle est recalculée plus bas
    # depuis les unités disponibles afin qu'une ancienne valeur (ex. 0) ne
    # puisse pas écraser le stock réel lors d'une simple édition.
    has_tracked_units = product_has_tracked_units(db, produit)
    if not has_tracked_units:
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

    # ➕ Ajout ou rattachement de nouveaux codes-barres si fournis.
    # Les codes scannés passent d'abord par le statut temporaire : ils doivent
    # donc être rattachés à la fiche au lieu d'être silencieusement ignorés.
    added_codes = []
    already_linked_codes = []
    if scanned_barcodes:
        try:
            barcodes = json.loads(scanned_barcodes)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Format JSON invalide pour scanned_barcodes",
            )
        if not isinstance(barcodes, list):
            raise HTTPException(
                status_code=400,
                detail="La liste des codes-barres est invalide",
            )

        normalized_barcodes = list(dict.fromkeys(
            code.strip() for code in barcodes
            if isinstance(code, str) and code.strip()
        ))
        conflicts = []
        moved_codes = []
        previous_product_ids = set()
        now = datetime.utcnow()
        for code in normalized_barcodes:
            unit = db.query(UniteProduit).filter(
                UniteProduit.enterprise_id == enterprise_id,
                or_(
                    UniteProduit.code_barre == code,
                    UniteProduit.tracabilite == code,
                ),
            ).first()
            if unit is not None:
                attachment = attach_reusable_unit(
                    unit,
                    produit,
                    enterprise_id=enterprise_id,
                    now=now,
                )
                if attachment.action == "already_linked":
                    already_linked_codes.append(code)
                    continue
                if not attachment.was_added:
                    conflicts.append(code)
                    continue
                if attachment.previous_product_id not in (None, produit.id):
                    previous_product_ids.add(attachment.previous_product_id)
                    moved_codes.append(code)
                added_codes.append(code)
                continue

            db.add(UniteProduit(
                produit_id=produit.id,
                enterprise_id=enterprise_id,
                tracabilite=code,
                code_barre=code,
                statut="disponible",
                date_creation=now,
            ))
            added_codes.append(code)

        if conflicts:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=(
                    "Certains codes-barres appartiennent déjà à une autre fiche : "
                    + ", ".join(conflicts[:5])
                ),
            )

        if added_codes:
            produit.a_des_barcodes = True
            db.flush()
            for previous_product_id in previous_product_ids:
                refresh_available_product_quantity(db, previous_product_id)
            produit.quantite = count_available_units(db, produit.id, enterprise_id)
            log_action(
                db=db,
                current_user=current_user,
                action="Ajout unités lors update",
                type_entite="produit",
                entite_id=produit.id,
                details=(
                    f"{len(added_codes)} unités ajoutées manuellement (update), "
                    f"dont {len(moved_codes)} réaffectée(s) depuis une autre fiche"
                ),
                commit=False,
            )

    # Garde-fou final : chaque fiche possédant des unités tracées conserve un
    # compteur égal aux unités disponibles, même si aucun nouveau code n'a été
    # ajouté durant cette modification.
    if produit.a_des_barcodes or has_tracked_units:
        produit.quantite = count_available_units(db, produit.id, enterprise_id)

    db.commit()

    log_action(
        db=db,
        current_user=current_user,
        action="Modification Produit",
        type_entite="produit",
        entite_id=produit.id,
        details=f"Produit de nom: {produit.nom} mis à jour (avec ou sans image)"
    )

    return {
        "message": "Produit modifié avec succès.",
        "added_count": len(added_codes),
        "added_codes": added_codes,
        "already_linked": already_linked_codes,
        "quantity": produit.quantite,
    }

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
    product = db.query(Produit).filter(
        Produit.id == produit_id,
        enterprise_scope_filter(Produit, current_user),
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    total = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.enterprise_id == product.enterprise_id,
    ).count()
    disponible = count_available_units(db, produit_id, product.enterprise_id)
    en_cours = db.query(UniteProduit).filter(
        UniteProduit.produit_id == produit_id,
        UniteProduit.enterprise_id == product.enterprise_id,
        func.lower(func.trim(func.coalesce(UniteProduit.statut, ""))).in_(
            ["en_cours", "en cours"]
        )
    ).count()
    return {"stock_total": total, "stock_reel": disponible, "stock_en_attente": en_cours}



