from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.user import ConsentRecord, User
from app.schemas.consent import ConsentCreate, ConsentRead

router = APIRouter(prefix="/v1/consents", tags=["consent"])


@router.get("", response_model=list[ConsentRead])
def list_consents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ConsentRecord]:
    return list(
        db.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user.id)
            .order_by(ConsentRecord.created_at.desc())
        )
    )


@router.post("", response_model=ConsentRead)
def set_consent(
    payload: ConsentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentRecord:
    """Record a consent decision. Latest row per ``consent_type`` is authoritative."""
    now = datetime.now(timezone.utc)
    record = ConsentRecord(
        user_id=user.id,
        consent_type=payload.consent_type,
        granted=payload.granted,
        granted_at=now if payload.granted else None,
        revoked_at=None if payload.granted else now,
        policy_version=get_settings().policy_version,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def has_consent(db: Session, user_id: str, consent_type: str) -> bool:
    row = db.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
        )
        .order_by(ConsentRecord.created_at.desc())
        .limit(1)
    )
    return bool(row and row.granted)
