from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.condition import SkinCondition
from app.models.enums import ConditionCategory
from app.schemas.condition import ConditionRead

router = APIRouter(prefix="/v1/conditions", tags=["conditions"])


@router.get("", response_model=list[ConditionRead])
def list_conditions(
    category: ConditionCategory | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SkinCondition]:
    stmt = select(SkinCondition).where(SkinCondition.is_active.is_(True))
    if category:
        stmt = stmt.where(SkinCondition.category == category)
    return list(db.scalars(stmt.order_by(SkinCondition.display_name)))


@router.get("/{slug}", response_model=ConditionRead)
def get_condition(slug: str, db: Session = Depends(get_db)) -> SkinCondition:
    cond = db.scalar(select(SkinCondition).where(SkinCondition.slug == slug))
    if cond is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condition not found")
    return cond
