from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.models.model_rapport import Rapport
from app.models.model_user import User, SubUser
from app.utils.security import get_current_user, get_current_sub_user
from app.schemas.rapport_schema import (
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
from app.services.enterprise_service import actor_enterprise_id, actor_owner_id, enterprise_scope_filter


router = APIRouter(prefix="/rapports", tags=["Rapports"])


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
    }




@router.get("/", response_model=List[RapportOut])
def list_rapports(
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    rapports = (
        db.query(Rapport)
        .options(joinedload(Rapport.user), joinedload(Rapport.sub_user))
        .filter(enterprise_scope_filter(Rapport, current_user))
        .order_by(Rapport.date_creation.desc())
        .all()
    )

    result = []
    for r in rapports:
        if r.sub_user:
            auteur = r.sub_user.username
            avatar_url = r.sub_user.avatar_url
            role = r.sub_user.role
            # print(f"🧪 sub_user_avatar: {avatar_url}")
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
                r.sub_user_id == current_user.id
                if not current_user.is_main_user
                else r.sub_user_id is None and r.user_id == current_user.id
            ),
            "is_edited": r.date_modification is not None,
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

    is_owner = (
        rapport.sub_user_id == current_user.id
        if not getattr(current_user, "is_main_user", False)
        else rapport.sub_user_id is None and rapport.user_id == current_user.id
    )
    if not is_owner:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez modifier que vos propres rapports",
        )

    if rapport.date_creation.date() != datetime.utcnow().date():
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
        "auteur": getattr(author, "username", None)
        or getattr(author, "email", None)
        or "Utilisateur",
        "avatar_url": getattr(author, "avatar_url", None),
        "role": getattr(author, "role", None)
        or ("Administrateur" if rapport.sub_user_id is None else "Utilisateur"),
        "is_mine": True,
        "is_edited": True,
    }



@router.delete("/{rapport_id}")
def delete_rapport(rapport_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    rapport = db.query(Rapport).filter(
        Rapport.id == rapport_id,
        enterprise_scope_filter(Rapport, current_user),
    ).first()

    if not rapport:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

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
