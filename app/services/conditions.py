from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.condition import SkinCondition


def _normalise(label: str) -> str:
    return label.strip().lower().replace(" ", "_").replace("-", "_")


def resolve_label(db: Session, raw_label: str) -> SkinCondition | None:
    """Map a model-native label to a catalogue row via slug or alias.

    Returns ``None`` when nothing matches — the pipeline then marks the
    prediction ``mapped_ok=False`` and triage treats the result as uncertain.
    """
    key = _normalise(raw_label)
    conditions = db.scalars(
        select(SkinCondition).where(SkinCondition.is_active.is_(True))
    ).all()
    for c in conditions:
        if c.slug == key:
            return c
    for c in conditions:
        if key in {_normalise(a) for a in (c.aliases or [])}:
            return c
    return None
