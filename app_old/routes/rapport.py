from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_rapport import Rapport
from app.models.model_user import User, SubUser
from app.utils.security import get_current_user, get_current_sub_user
from app.schemas.rapport_schema import RapportCreate, RapportOut
from app.utils.permissions import All_required
from app.utils.logger import log_action
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from sqlalchemy import or_
from datetime import datetime, date


router = APIRouter(prefix="/rapports", tags=["Rapports"])

@router.post("/", response_model=RapportOut)
def create_rapport(
    data: RapportCreate, 
    db: Session = Depends(get_db), 
    current_user = Depends(All_required())
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    rapport = Rapport(
        contenu=data.contenu,
        user_id=parent_user_id
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
        "user_id": rapport.user_id,
        "sub_user_id": None,
        "auteur": current_user.username or current_user.email
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
        user_id=current_sub.parent_user_id  # 👈 important !
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
        "user_id": rapport.user_id,
        "sub_user_id": rapport.sub_user_id,
        "auteur": current_sub.username
    }




@router.get("/", response_model=List[RapportOut])
def list_rapports(
    db: Session = Depends(get_db),
    current_user = Depends(All_required())
):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id

    rapports = db.query(Rapport)\
        .filter(
            or_(
                Rapport.user_id == parent_user_id,
                Rapport.sub_user.has(parent_user_id=parent_user_id)
            )
        )\
        .order_by(Rapport.date_creation.desc())\
        .all()

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
            role = "Main user"
        else:
            auteur = "Inconnu"
            avatar_url = None
            role = "Inconnu"
        


        result.append({
            "id": r.id,
            "contenu": r.contenu,
            "date_creation": r.date_creation,
            "user_id": r.user_id,
            "sub_user_id": r.sub_user_id,
            "auteur": auteur,
            "avatar_url": avatar_url,
            "role": role
        })

    return result



@router.delete("/{rapport_id}")
def delete_rapport(rapport_id: int, db: Session = Depends(get_db), current_user=Depends(All_required())):
    parent_user_id = current_user.parent_user_id if not current_user.is_main_user else current_user.id
    rapport = db.query(Rapport).filter(Rapport.id == rapport_id).first()

    if not rapport:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    # Optionnel : vérifier que le rapport appartient bien à ce user
    if rapport.user_id != parent_user_id:
        raise HTTPException(status_code=403, detail="Accès interdit")

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