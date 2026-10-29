from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.model_app_download import AppDownloadSetting
from app.models.model_user import User
from app.schemas.app_download_schema import (
    SUPPORTED_PLATFORMS,
    AppDownloadCatalogOut,
    AppDownloadOut,
    AppDownloadUpdate,
)
from app.utils.security import require_super_user


router = APIRouter(prefix="/app-downloads", tags=["App downloads"])


def _default_platform(platform: str) -> AppDownloadOut:
    return AppDownloadOut(platform=platform, enabled=False)


def _catalog(db: Session) -> AppDownloadCatalogOut:
    rows = {
        row.platform: AppDownloadOut.model_validate(row)
        for row in db.query(AppDownloadSetting)
        .filter(AppDownloadSetting.platform.in_(SUPPORTED_PLATFORMS))
        .all()
    }
    return AppDownloadCatalogOut(
        android=rows.get("android", _default_platform("android")),
        windows=rows.get("windows", _default_platform("windows")),
    )


@router.get("/public", response_model=AppDownloadCatalogOut)
def get_public_app_downloads(
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "public, max-age=300"
    return _catalog(db)


@router.get("/admin", response_model=AppDownloadCatalogOut)
def get_app_download_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
):
    return _catalog(db)


@router.put("/admin/{platform}", response_model=AppDownloadOut)
def update_app_download_setting(
    platform: str,
    payload: AppDownloadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_user),
):
    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail="Plateforme non prise en charge")

    setting = (
        db.query(AppDownloadSetting)
        .filter(AppDownloadSetting.platform == platform)
        .first()
    )
    if setting is None:
        setting = AppDownloadSetting(platform=platform)
        db.add(setting)

    for field, value in payload.model_dump().items():
        setattr(setting, field, value)
    setting.updated_at = datetime.utcnow()
    setting.updated_by_user_id = current_user.id

    db.commit()
    db.refresh(setting)
    return setting
