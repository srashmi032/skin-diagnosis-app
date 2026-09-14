from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import ConditionCategory, TriageLevel


class SkinCondition(UUIDPrimaryKey, Timestamps, Base):
    """Reference catalogue of skin conditions the system can talk about.

    This is the *controlled vocabulary* for results. A raw model label is only
    surfaced to the user after it maps to a row here; unmapped labels are treated
    as "uncertain -> refer". Editing this table (not code) tunes the educational
    copy, triage defaults, and which findings force a referral.
    """

    __tablename__ = "skin_conditions"

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # alternate model labels / lay terms
    category: Mapped[ConditionCategory] = mapped_column(
        Enum(ConditionCategory, native_enum=False, length=20)
    )

    summary: Mapped[str] = mapped_column(Text)
    common_symptoms: Mapped[list] = mapped_column(JSON, default=list)
    typical_body_sites: Mapped[list] = mapped_column(JSON, default=list)
    self_care_guidance: Mapped[str | None] = mapped_column(Text)
    when_to_see_doctor: Mapped[str | None] = mapped_column(Text)
    reference_url: Mapped[str | None] = mapped_column(String(512))

    default_triage_level: Mapped[TriageLevel] = mapped_column(
        Enum(TriageLevel, native_enum=False, length=12), default=TriageLevel.routine
    )
    # e.g. suspected melanoma / BCC: any non-trivial probability => urgent referral,
    # never self-care copy.
    is_referral_trigger: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
