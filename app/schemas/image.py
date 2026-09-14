from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ImageStatus


class ImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    content_type: str
    byte_size: int
    width: int | None
    height: int | None
    body_site: str | None
    status: ImageStatus
    quality_report: dict | None
    captured_at: datetime | None
    created_at: datetime


class ImageDownloadUrl(BaseModel):
    url: str
    expires_in: int
