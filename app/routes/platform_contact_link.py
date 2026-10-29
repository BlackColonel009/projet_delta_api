from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_platform_contact_link import PlatformContactLink
from app.models.model_user import User
from app.schemas.platform_contact_link_schema import (
    PlatformContactLinkOut,
    PlatformContactLinkPayload,
)
from app.utils.security import require_super_user


router = APIRouter(
    prefix="/platform-contact-links",
    tags=["Platform contact links"],
)


def _ordered_query(db: Session):
    return db.query(PlatformContactLink).order_by(
        PlatformContactLink.sort_order,
        PlatformContactLink.id,
    )


@router.get("/public", response_model=list[PlatformContactLinkOut])
def list_public_contact_links(
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "public, max-age=300"
    return _ordered_query(db).filter(PlatformContactLink.is_visible.is_(True)).all()


@router.get("/admin", response_model=list[PlatformContactLinkOut])
def list_contact_links_for_admin(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
):
    return _ordered_query(db).all()


@router.post(
    "/admin",
    response_model=PlatformContactLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_contact_link(
    payload: PlatformContactLinkPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_user),
):
    link = PlatformContactLink(
        **payload.model_dump(),
        updated_by_user_id=current_user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.put("/admin/{link_id}", response_model=PlatformContactLinkOut)
def update_contact_link(
    link_id: int,
    payload: PlatformContactLinkPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_user),
):
    link = db.query(PlatformContactLink).filter(PlatformContactLink.id == link_id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Canal de contact introuvable")
    for field, value in payload.model_dump().items():
        setattr(link, field, value)
    link.updated_at = datetime.utcnow()
    link.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(link)
    return link


@router.delete("/admin/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact_link(
    link_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
):
    link = db.query(PlatformContactLink).filter(PlatformContactLink.id == link_id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Canal de contact introuvable")
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
