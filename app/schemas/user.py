from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    date_of_birth: date | None
    skin_type: str | None
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: date | None = None
    skin_type: str | None = None
