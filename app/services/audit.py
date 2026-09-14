from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    context: dict | None = None,
) -> None:
    """Append one audit row. Caller owns the transaction commit."""
    db.add(
        AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            context=context,
        )
    )
