from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import ConsentType, UserRole


class User(UUIDPrimaryKey, Timestamps, Base):
    """An account. ``role`` gates what the holder may do (see app/deps.py)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20), default=UserRole.patient
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Optional clinical context that improves triage quality.
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    skin_type: Mapped[str | None] = mapped_column(String(20))  # Fitzpatrick I–VI or oily/dry/…

    consents: Mapped[list["ConsentRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    images: Mapped[list["SkinImage"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["AnalysisRequest"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )


class ConsentRecord(UUIDPrimaryKey, Timestamps, Base):
    """Append-only-ish record of a consent grant/revocation.

    We keep the row and set ``revoked_at`` rather than deleting, so we can prove
    what the user agreed to and when.
    """

    __tablename__ = "consent_records"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(ConsentType, native_enum=False, length=32)
    )
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(20), default="1.0")

    user: Mapped["User"] = relationship(back_populates="consents")
