from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.enums import ImageStatus
from app.models.image import SkinImage
from app.models.user import User
from app.routers.consents import has_consent
from app.schemas.image import ImageDownloadUrl, ImageRead
from app.services import audit
from app.services.image_qc import run_quality_check
from app.services.storage import get_storage

router = APIRouter(prefix="/v1/images", tags=["images"])


@router.post("", response_model=ImageRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    body_site: str | None = Form(default=None),
    captured_at: datetime | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkinImage:
    settings = get_settings()

    if not has_consent(db, user.id, "image_storage") or not has_consent(
        db, user.id, "ai_processing"
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Consent required: grant 'image_storage' and 'ai_processing' first "
            "(POST /v1/consents).",
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty file")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large")

    content_type = file.content_type or "application/octet-stream"
    passed, report = run_quality_check(data, content_type)

    checksum = hashlib.sha256(data).hexdigest()
    storage = get_storage()
    key = f"{user.id}/{checksum}"
    storage.save(key, data)

    image = SkinImage(
        user_id=user.id,
        storage_backend=storage.backend_name,
        storage_key=key,
        content_type=report.get("sniffed_content_type") or content_type,
        byte_size=len(data),
        checksum_sha256=checksum,
        width=report.get("width"),
        height=report.get("height"),
        body_site=body_site,
        captured_at=captured_at,
        status=ImageStatus.ready if passed else ImageStatus.quality_failed,
        quality_report=report,
    )
    db.add(image)
    db.flush()
    audit.record(
        db,
        action="image.upload",
        resource_type="skin_image",
        resource_id=image.id,
        actor_id=user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        context={"quality_passed": passed},
    )
    db.commit()
    db.refresh(image)
    return image


@router.get("", response_model=list[ImageRead])
def list_images(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SkinImage]:
    return list(
        db.scalars(
            select(SkinImage)
            .where(SkinImage.user_id == user.id, SkinImage.deleted_at.is_(None))
            .order_by(SkinImage.created_at.desc())
        )
    )


def _owned_image(image_id: str, user: User, db: Session) -> SkinImage:
    image = db.get(SkinImage, image_id)
    if image is None or image.user_id != user.id or image.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    return image


@router.get("/{image_id}", response_model=ImageRead)
def get_image(
    image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SkinImage:
    return _owned_image(image_id, user, db)


@router.get("/{image_id}/download-url", response_model=ImageDownloadUrl)
def get_download_url(
    image_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ImageDownloadUrl:
    image = _owned_image(image_id, user, db)
    url, ttl = get_storage().signed_url(image.storage_key)
    return ImageDownloadUrl(url=url, expires_in=ttl)


@router.get("/raw/{user_prefix}/{checksum}")
def download_raw(
    user_prefix: str,
    checksum: str,
    expires: int,
    signature: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Serve image bytes for a valid signed URL. No bearer token — the HMAC
    signature is the capability (same model as an S3 pre-signed URL).
    """
    key = f"{user_prefix}/{checksum}"
    storage = get_storage()
    if not storage.verify_signature(key, expires, signature):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid or expired signature")
    image = db.scalar(select(SkinImage).where(SkinImage.storage_key == key))
    if image is None or image.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    try:
        data = storage.load(key)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image bytes missing")
    audit.record(
        db,
        action="image.download",
        resource_type="skin_image",
        resource_id=image.id,
        actor_id=image.user_id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return Response(content=data, media_type=image.content_type)


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete the row and hard-delete the bytes (right-to-erasure)."""
    image = _owned_image(image_id, user, db)
    try:
        get_storage().delete(image.storage_key)
    except FileNotFoundError:
        pass
    image.deleted_at = datetime.now(timezone.utc)
    image.status = ImageStatus.deleted
    audit.record(
        db,
        action="image.delete",
        resource_type="skin_image",
        resource_id=image.id,
        actor_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
