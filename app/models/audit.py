from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, Base):
    """Immutable trail of security-relevant actions on sensitive resources
    (image upload/view/download/delete, analysis create/view, consent changes).

    Written by app.services.audit; never updated or deleted by application code.
    """

    __tablename__ = "audit_logs"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "image.download"
    resource_type: Mapped[str] = mapped_column(String(48))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(256))
    context: Mapped[dict | None] = mapped_column(JSON)
