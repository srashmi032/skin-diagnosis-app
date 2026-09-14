from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnalysisStatus, FlagCode, TriageLevel
from app.schemas.condition import ConditionRead


class AnalysisCreate(BaseModel):
    image_id: str
    # Free-form but validated keys the triage engine understands.
    questionnaire: Questionnaire | None = None


class Questionnaire(BaseModel):
    duration_days: int | None = Field(default=None, ge=0, le=36500)
    itch: bool | None = None
    pain: bool | None = None
    spreading: bool | None = None
    bleeding: bool | None = None
    recent_change: bool | None = None  # size/shape/colour changed recently
    prior_similar: bool | None = None


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    raw_label: str
    confidence: float
    rank: int
    is_primary: bool
    mapped_ok: bool
    condition: ConditionRead | None


class TriageFlagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: FlagCode
    level: TriageLevel
    message: str


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    image_id: str
    status: AnalysisStatus
    triage_level: TriageLevel | None
    model_version: str
    created_at: datetime


class AnalysisRead(AnalysisSummary):
    inference_adapter: str
    questionnaire: dict | None
    triage_rationale: str | None
    disclaimer_version: str
    disclaimer: str = ""  # filled from settings by the router
    error_detail: str | None
    latency_ms: int | None
    predictions: list[PredictionRead]
    flags: list[TriageFlagRead]


AnalysisCreate.model_rebuild()
