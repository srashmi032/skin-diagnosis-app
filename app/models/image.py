from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import ImageStatus


class SkinImage(UUIDPrimaryKey, Timestamps, Base):
    """Metadata for one uploaded photo. The bytes live in object storage, keyed
    by ``storage_key``; this table never holds image data itself.
    """

    __tablename__ = "skin_images"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # storage pointer
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_key: Mapped[str] = mapped_column(String(512))

    # intrinsic file facts (used for dedupe, QC, and abuse limits)
    content_type: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    # user-supplied context
    body_site: Mapped[str | None] = mapped_column(String(64))  # face, forearm, scalp, …
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # QC outcome
    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, native_enum=False, length=20), default=ImageStatus.uploaded
    )
    quality_report: Mapped[dict | None] = mapped_column(JSON)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="images")  # noqa: F821
    analyses: Mapped[list["AnalysisRequest"]] = relationship(  # noqa: F821
        back_populates="image"
    )
