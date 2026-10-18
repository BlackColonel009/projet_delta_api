from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.models.model_rapport import Rapport
from app.models.model_enterprise import Enterprise
from app.models.model_user import User, SubUser
from app.utils.security import get_current_user, get_current_sub_user
from app.schemas.rapport_schema import (
    AutomaticReportSettingsOut,
    AutomaticReportSettingsUpdate,
    RapportCreate,
    RapportOut,
    RapportSharingOut,
    RapportSharingUpdate,
    RapportUpdate,
)
from app.utils.permissions import All_required
from app.utils.logger import log_action
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter
from app.services.automatic_work_report_service import (
    AUTOMATIC_SOURCE,
    generate_daily_work_report,
)


router = APIRouter(prefix="/rapports", tags=["Rapports"])

_AUTOMATIC_REPORT_DEFAULTS = {
    "detail_level": "detailed",
    "include_amounts": True,
    "include_sales": True,
    "include_products": True,
    "include_product_units": True,
    "include_interventions": True,
    "include_consignments": True,
    "include_payments": True,
    "include_status_changes": True,
    "include_maintenance": True,
    "publish_when_empty": True,
}


def _automatic_report_config(enterprise: Enterprise) -> dict:
    return {
        **_AUTOMATIC_REPORT_DEFAULTS,
        **(enterprise.automatic_work_report_config or {}),
    }


def _company_owner(db: Session, current_user) -> User:
    if getattr(current_user, "is_main_user", False):
        return current_user
    owner = db.query(User).filter(User.id == current_user.parent_user_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    return owner


def _can_manage_sharing(current_user) -> bool:
    return bool(
        getattr(current_user, "is_main_user", False)
        or getattr(current_user, "is_superuser", False)
    )


def _can_manage_automatic_report(current_user) -> bool:
    return bool(
        getattr(current_user, "is_main_user", False)
        or str(getattr(current_user, "role", "")).strip().lower() == "admin"
    )

@router.post("/", response_model=RapportOut)
def create_rapport(
    data: RapportCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(All_required())
):
    parent_user_id = actor_owner_id(current_user)

    rapport = Rapport(
        contenu=data.contenu,
        user_id=parent_user_id,
        enterprise_id=actor_enterprise_id(current_user),
    )

    db.add(rapport)
    db.commit()
    db.refresh(rapport)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout Rapport",
        type_entite="rapport",
        entite_id=rapport.id,
        details=f"{rapport.contenu})"
    )

    return {
        "id": rapport.id,
        "contenu": rapport.contenu,
        "date_creation": rapport.date_creation,
        "date_modification": rapport.date_modification,
        "user_id": rapport.user_id,
        "sub_user_id": None,
        "auteur": current_user.username or current_user.email,
        "avatar_url": current_user.avatar_url,
        "role": "Administrateur",
        "is_mine": True,
        "is_edited": False,
        "is_automatic": False,
    }


@router.post("/sub", response_model=RapportOut)
def create_rapport_sub(
    data: RapportCreate, 
    db: Session = Depends(get_db), 
    current_sub: SubUser = Depends(get_current_sub_user),
    current_user = Depends(All_required())
):
    rapport = Rapport(
        contenu=data.contenu,
        sub_user_id=current_sub.id,
        user_id=current_sub.parent_user_id,
        enterprise_id=actor_enterprise_id(current_user),
    )

    db.add(rapport)
    db.commit()
    db.refresh(rapport)
    
    log_action(
        db=db,
        current_user=current_user,
        action="Ajout Rapport",
        type_entite="rapport",
        entite_id=rapport.id,
        details=f"{rapport.contenu})"
    )
    
    return {
        "id": rapport.id,
        "contenu": rapport.contenu,
        "date_creation": rapport.date_creation,
        "date_modification": rapport.date_modification,
        "user_id": rapport.user_id,
        "sub_user_id": rapport.sub_user_id,
        "auteur": current_sub.username,
        "avatar_url": current_sub.avatar_url,
        "role": current_sub.role,
        "is_mine": True,
        "is_edited": False,
        "is_automatic": False,
    }




@router.get("/", response_model=List[RapportOut])
def list_rapports(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    rapports = (
        db.query(Rapport)
        .options(joinedload(Rapport.user), joinedload(Rapport.sub_user))
        .filter(enterprise_scope_filter(Rapport, current_user))
        .order_by(Rapport.date_creation.desc())
    )
    if offset:
        rapports = rapports.offset(offset)
    rapports = rapports.limit(limit)
    rapports = rapports.all()

    result = []
    for r in rapports:
        if r.sub_user:
            auteur = r.sub_user.username
            avatar_url = r.sub_user.avatar_url
            role = r.sub_user.role
            # print(f"🧪 sub_user_avatar: {avatar_url}")
        elif r.source == AUTOMATIC_SOURCE:
            auteur = "Trade Care"
            avatar_url = None
            role = "Rapport automatique"
        elif r.user:
            auteur = r.user.username or r.user.email
            avatar_url = r.user.avatar_url
            role = "Administrateur"
        else:
            auteur = "Inconnu"
            avatar_url = None
            role = "Inconnu"
        


        result.append({
            "id": r.id,
            "contenu": r.contenu,
            "date_creation": r.date_creation,
            "date_modification": r.date_modification,
            "user_id": r.user_id,
            "sub_user_id": r.sub_user_id,
            "auteur": auteur,
            "avatar_url": avatar_url,
            "role": role,
            "is_mine": (
                _can_manage_automatic_report(current_user)
                if r.source == AUTOMATIC_SOURCE else (
                r.sub_user_id == current_user.id
                if not current_user.is_main_user
                else r.sub_user_id is None and r.user_id == current_user.id
            ),
            ),
            "is_edited": r.date_modification is not None,
            "is_automatic": r.source == AUTOMATIC_SOURCE,
        })

    return result


@router.get("/settings/sharing", response_model=RapportSharingOut)
def get_report_sharing_settings(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    owner = _company_owner(db, current_user)
    return {
        "enabled": bool(owner.report_sharing_enabled),
        "can_manage": _can_manage_sharing(current_user),
    }


@router.put("/settings/sharing", response_model=RapportSharingOut)
def update_report_sharing_settings(
    data: RapportSharingUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    if not _can_manage_sharing(current_user):
        raise HTTPException(
            status_code=403,
            detail="Seul le compte principal peut gérer le partage des rapports",
        )
    owner = _company_owner(db, current_user)
    owner.report_sharing_enabled = data.enabled
    db.commit()
    db.refresh(owner)
    return {"enabled": bool(owner.report_sharing_enabled), "can_manage": True}


def _report_enterprise(db: Session, current_user) -> Enterprise:
    enterprise = db.query(Enterprise).filter(
        Enterprise.id == actor_enterprise_id(current_user),
        Enterprise.status == "active",
    ).first()
    if enterprise is None:
        raise HTTPException(
            status_code=404,
            detail="Entreprise active introuvable",
        )
    return enterprise


@router.get("/automation/settings", response_model=AutomaticReportSettingsOut)
def get_automatic_report_settings(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    owner = _company_owner(db, current_user)
    enterprise = _report_enterprise(db, current_user)
    hour = (
        owner.daily_report_reminder_hour
        if enterprise.automatic_work_report_inherit_time
        else enterprise.automatic_work_report_hour
    )
    minute = (
        owner.daily_report_reminder_minute
        if enterprise.automatic_work_report_inherit_time
        else enterprise.automatic_work_report_minute
    )
    return {
        "enabled": bool(enterprise.automatic_work_report_enabled),
        "inherit_time": bool(enterprise.automatic_work_report_inherit_time),
        "hour": hour,
        "minute": minute,
        "timezone": enterprise.timezone,
        "can_manage": _can_manage_automatic_report(current_user),
        **_automatic_report_config(enterprise),
    }


@router.put("/automation/settings", response_model=AutomaticReportSettingsOut)
def update_automatic_report_settings(
    data: AutomaticReportSettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    if not _can_manage_automatic_report(current_user):
        raise HTTPException(
            status_code=403,
            detail="Seuls le compte principal et le rôle admin peuvent configurer le rapport automatique",
        )
    owner = _company_owner(db, current_user)
    enterprise = _report_enterprise(db, current_user)
    enterprise.automatic_work_report_enabled = data.enabled
    enterprise.automatic_work_report_inherit_time = data.inherit_time
    enterprise.automatic_work_report_hour = data.hour
    enterprise.automatic_work_report_minute = data.minute
    enterprise.automatic_work_report_config = {
        "detail_level": data.detail_level,
        "include_amounts": data.include_amounts,
        "include_sales": data.include_sales,
        "include_products": data.include_products,
        "include_product_units": data.include_product_units,
        "include_interventions": data.include_interventions,
        "include_consignments": data.include_consignments,
        "include_payments": data.include_payments,
        "include_status_changes": data.include_status_changes,
        "include_maintenance": data.include_maintenance,
        "publish_when_empty": data.publish_when_empty,
    }
    db.commit()
    hour = owner.daily_report_reminder_hour if data.inherit_time else data.hour
    minute = owner.daily_report_reminder_minute if data.inherit_time else data.minute
    return {
        "enabled": bool(enterprise.automatic_work_report_enabled),
        "inherit_time": bool(enterprise.automatic_work_report_inherit_time),
        "hour": hour,
        "minute": minute,
        "timezone": enterprise.timezone,
        "can_manage": True,
        **_automatic_report_config(enterprise),
    }


@router.post("/automation/generate-now", response_model=RapportOut)
def generate_automatic_report_now(
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    """Test contrôlé : génère ou actualise le rapport automatique du jour."""
    if not _can_manage_automatic_report(current_user):
        raise HTTPException(
            status_code=403,
            detail="Seuls le compte principal et le rôle admin peuvent lancer le rapport automatique",
        )
    enterprise = _report_enterprise(db, current_user)
    try:
        report_day = datetime.now(ZoneInfo(enterprise.timezone)).date()
    except ZoneInfoNotFoundError:
        report_day = datetime.utcnow().date()
    report = generate_daily_work_report(
        db,
        enterprise,
        report_day,
        refresh_existing=False,
    )
    if report is None:
        raise HTTPException(
            status_code=409,
            detail="Aucune activité aujourd’hui et la publication des rapports vides est désactivée",
        )
    return {
        "id": report.id,
        "contenu": report.contenu,
        "date_creation": report.date_creation,
        "date_modification": report.date_modification,
        "user_id": report.user_id,
        "sub_user_id": None,
        "auteur": "Trade Care",
        "avatar_url": None,
        "role": "Rapport automatique",
        "is_mine": True,
        "is_edited": report.date_modification is not None,
        "is_automatic": True,
    }


@router.put("/{rapport_id}", response_model=RapportOut)
def update_rapport(
    rapport_id: int,
    data: RapportUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(All_required()),
):
    owner = _company_owner(db, current_user)
    rapport = db.query(Rapport).filter(
        Rapport.id == rapport_id,
        enterprise_scope_filter(Rapport, current_user),
    ).first()
    if not rapport:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    is_automatic = rapport.source == AUTOMATIC_SOURCE
    is_owner = (
        rapport.sub_user_id == current_user.id
        if not getattr(current_user, "is_main_user", False)
        else rapport.sub_user_id is None and rapport.user_id == current_user.id
    )
    if is_automatic:
        is_owner = _can_manage_automatic_report(current_user)
    if not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez modifier que vos propres rapports",
        )

    if is_automatic:
        enterprise = _report_enterprise(db, current_user)
        try:
            today = datetime.now(ZoneInfo(enterprise.timezone)).date()
        except ZoneInfoNotFoundError:
            today = datetime.utcnow().date()
        editable_today = rapport.source_date == today
    else:
        editable_today = rapport.date_creation.date() == datetime.utcnow().date()
    if not editable_today:
        raise HTTPException(
            status_code=403,
            detail="Un rapport ne peut être modifié que le jour de sa publication",
        )

    previous_content = rapport.contenu
    rapport.contenu = data.contenu
    rapport.date_modification = datetime.utcnow()
    db.commit()
    db.refresh(rapport)

    log_action(
        db=db,
        current_user=current_user,
        action="Modification Rapport",
        type_entite="rapport",
        entite_id=rapport.id,
        details=(
            f"Rapport {rapport.id} modifié le jour de sa publication. "
            f"Ancien contenu : {previous_content} | Nouveau contenu : {rapport.contenu}"
        ),
    )

    author = rapport.sub_user if rapport.sub_user_id else rapport.user
    return {
        "id": rapport.id,
        "contenu": rapport.contenu,
        "date_creation": rapport.date_creation,
        "date_modification": rapport.date_modification,
        "user_id": rapport.user_id,
        "sub_user_id": rapport.sub_user_id,
        "auteur": "Trade Care" if is_automatic else getattr(author, "username", None)
        or getattr(author, "email", None)
        or "Utilisateur",
        "avatar_url": None if is_automatic else getattr(author, "avatar_url", None),
        "role": "Rapport automatique" if is_automatic else getattr(author, "role", None)
        or ("Administrateur" if rapport.sub_user_id is None else "Utilisateur"),
        "is_mine": True,
        "is_edited": True,
        "is_automatic": is_automatic,
    }



@router.delete("/{rapport_id}")
def delete_rapport(rapport_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    rapport = db.query(Rapport).filter(
        Rapport.id == rapport_id,
        enterprise_scope_filter(Rapport, current_user),
    ).first()

    if not rapport:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    if rapport.source == AUTOMATIC_SOURCE:
        raise HTTPException(
            status_code=403,
            detail="Un rapport automatique Trade Care ne peut pas être supprimé",
        )

    if not current_user.is_main_user and rapport.sub_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez supprimer que vos propres rapports",
        )

    db.delete(rapport)
    db.commit()

    return {"message": "Rapport supprimé avec succès"}

# @router.get("/export/pdf", response_class=StreamingResponse)
# def export_rapports_pdf(
#     db: Session = Depends(get_db),
#     current_user=Depends(All_required())
# ):
#     today = date.today()

#     if current_user.is_main_user:
#         rapports = db.query(Rapport).filter(
#             Rapport.user_id == current_user.id,
#             Rapport.date_creation >= datetime(today.year, today.month, today.day)
#         ).order_by(Rapport.date_creation.asc()).all()
#     else:
#         rapports = db.query(Rapport).filter(
#             Rapport.sub_user_id == current_user.id,
#             Rapport.date_creation >= datetime(today.year, today.month, today.day)
#         ).order_by(Rapport.date_creation.asc()).all()

#     buffer = BytesIO()
#     c = canvas.Canvas(buffer, pagesize=A4)
#     width, height = A4
#     y = height - 50

#     c.setFont("Helvetica-Bold", 16)
#     c.drawString(50, y, f"Rapports du {today.strftime('%d/%m/%Y')}")
#     y -= 30
#     c.setFont("Helvetica", 12)

#     for r in rapports:
#         auteur = r.user.username if r.user else r.sub_user.username if r.sub_user else "Anonyme"
#         c.drawString(50, y, f"- {auteur} à {r.date_creation.strftime('%H:%M')} : {r.contenu}")
#         y -= 20
#         if y < 50:
#             c.showPage()
#             y = height - 50
#             c.setFont("Helvetica", 12)

#     c.save()
#     buffer.seek(0)

#     filename = f\"rapport_{today.strftime('%d%m%Y')}.pdf\"
#     return StreamingResponse(
#         buffer,
#         media_type=\"application/pdf\",
#         headers={\"Content-Disposition\": f\"inline; filename={filename}\"}
    # )
