from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConditionCategory, TriageLevel


class ConditionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    display_name: str
    category: ConditionCategory
    summary: str
    common_symptoms: list[str]
    typical_body_sites: list[str]
    self_care_guidance: str | None
    when_to_see_doctor: str | None
    reference_url: str | None
    default_triage_level: TriageLevel
    is_referral_trigger: bool
