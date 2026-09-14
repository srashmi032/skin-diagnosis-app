"""Shared FastAPI dependencies: DB session, current user, role guards."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.security import decode_token

__all__ = ["get_db", "get_current_user", "require_role", "CurrentUser"]

_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(creds.credentials)
        user_id = payload.get("sub")
    except Exception:  # noqa: BLE001
        raise cred_exc
    if not user_id:
        raise cred_exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise cred_exc
    return user


def require_role(*roles: UserRole):
    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return user

    return _guard


CurrentUser = Depends(get_current_user)
