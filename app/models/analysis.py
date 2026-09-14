from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import AnalysisStatus, FlagCode, TriageLevel, UserRole


class AnalysisRequest(UUIDPrimaryKey, Timestamps, Base):
    """One run of the pipeline against one image: QC -> inference -> mapping ->
    triage. Holds the *outcome envelope*; individual condition guesses are rows
    in ``analysis_predictions``, safety flags in ``triage_flags``.
    """

    __tablename__ = "analysis_requests"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    image_id: Mapped[str] = mapped_column(
        ForeignKey("skin_images.id", ondelete="RESTRICT"), index=True
    )

    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, native_enum=False, length=12),
        default=AnalysisStatus.pending,
        index=True,
    )

    # reproducibility: which model produced this result
    inference_adapter: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str] = mapped_column(String(64))

    # optional symptom questionnaire answers (itch, duration_days, pain, spreading,
    # bleeding, recent_change, ...). Feeds the triage rules.
    questionnaire: Mapped[dict | None] = mapped_column(JSON)

    # triage summary (derived from predictions + questionnaire + image QC)
    triage_level: Mapped[TriageLevel | None] = mapped_column(
        Enum(TriageLevel, native_enum=False, length=12)
    )
    triage_rationale: Mapped[str | None] = mapped_column(Text)
    disclaimer_version: Mapped[str] = mapped_column(String(20), default="1.0")

    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="analyses")  # noqa: F821
    image: Mapped["SkinImage"] = relationship(back_populates="analyses")  # noqa: F821
    predictions: Mapped[list["AnalysisPrediction"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="AnalysisPrediction.rank",
    )
    flags: Mapped[list["TriageFlag"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["AnalysisFeedback"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class AnalysisPrediction(UUIDPrimaryKey, Timestamps, Base):
    """A single ranked condition guess for an analysis."""

    __tablename__ = "analysis_predictions"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_requests.id", ondelete="CASCADE"), index=True
    )
    # nullable: the raw label may not map to a known condition (SET NULL keeps the
    # row so we can see what the model said and how often mapping fails).
    condition_id: Mapped[str | None] = mapped_column(
        ForeignKey("skin_conditions.id", ondelete="SET NULL")
    )

    raw_label: Mapped[str] = mapped_column(String(128))  # exact string from the model
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    rank: Mapped[int] = mapped_column(Integer)  # 1 = most likely
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    mapped_ok: Mapped[bool] = mapped_column(Boolean, default=True)

    analysis: Mapped["AnalysisRequest"] = relationship(back_populates="predictions")
    condition: Mapped["SkinCondition | None"] = relationship()  # noqa: F821


class TriageFlag(UUIDPrimaryKey, Timestamps, Base):
    """A safety signal raised during triage (why the user is being told to see
    someone, or why confidence is being downplayed).
    """

    __tablename__ = "triage_flags"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_requests.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[FlagCode] = mapped_column(Enum(FlagCode, native_enum=False, length=32))
    level: Mapped[TriageLevel] = mapped_column(
        Enum(TriageLevel, native_enum=False, length=12)
    )
    message: Mapped[str] = mapped_column(Text)

    analysis: Mapped["AnalysisRequest"] = relationship(back_populates="flags")


class AnalysisFeedback(UUIDPrimaryKey, Timestamps, Base):
    """Feedback on a result — from the patient (was this helpful?) or a clinician
    (was this correct? what was it actually?). Drives quality metrics and future
    model training sets.
    """

    __tablename__ = "analysis_feedback"

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_requests.id", ondelete="CASCADE"), index=True
    )
    submitted_by_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    submitter_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20)
    )

    helpfulness_rating: Mapped[int | None] = mapped_column(Integer)  # 1..5
    was_accurate: Mapped[bool | None] = mapped_column(Boolean)
    corrected_condition_id: Mapped[str | None] = mapped_column(
        ForeignKey("skin_conditions.id", ondelete="SET NULL")
    )
    comment: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped["AnalysisRequest"] = relationship(back_populates="feedback")
