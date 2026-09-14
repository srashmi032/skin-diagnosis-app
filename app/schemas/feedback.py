from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import UserRole


class FeedbackCreate(BaseModel):
    helpfulness_rating: int | None = Field(default=None, ge=1, le=5)
    was_accurate: bool | None = None
    corrected_condition_slug: str | None = None
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "FeedbackCreate":
        if not any(
            v is not None
            for v in (
                self.helpfulness_rating,
                self.was_accurate,
                self.corrected_condition_slug,
                self.comment,
            )
        ):
            raise ValueError("feedback must contain at least one field")
        return self


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    submitter_role: UserRole
    helpfulness_rating: int | None
    was_accurate: bool | None
    corrected_condition_id: str | None
    comment: str | None
    created_at: datetime
