from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConsentType


class ConsentCreate(BaseModel):
    consent_type: ConsentType
    granted: bool = True


class ConsentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    consent_type: ConsentType
    granted: bool
    granted_at: datetime | None
    revoked_at: datetime | None
    policy_version: str
