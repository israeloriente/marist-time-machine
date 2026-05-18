"""Auth dependency: validate Supabase-issued JWTs (HS256 with JWT_SECRET)."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status

from .config import settings


@dataclass
class User:
    id: str
    email: str | None
    role: str
    is_admin: bool = False


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    return token


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        settings().jwt_secret,
        algorithms=["HS256"],
        audience="authenticated",
    )


def _user_from_payload(payload: dict) -> User:
    # Supabase puts immutable, server-side claims in app_metadata. User-editable
    # claims live in user_metadata (NEVER use those for authorization).
    app_meta = payload.get("app_metadata") or {}
    app_role = app_meta.get("role") if isinstance(app_meta, dict) else None
    return User(
        id=payload["sub"],
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
        is_admin=app_role == "admin",
    )


def current_user(request: Request) -> User:
    token = _extract_token(request)
    try:
        payload = _decode(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
        ) from exc
    return _user_from_payload(payload)


def require_admin(request: Request) -> User:
    user = current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="acesso restrito a administradores",
        )
    return user


CurrentUser = Depends(current_user)
RequireAdmin = Depends(require_admin)


def optional_user(request: Request) -> User | None:
    """Like current_user but never raises — returns None when no/invalid token.

    Used by endpoints that must serve both authenticated app users and the
    public kiosk page.
    """
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = _decode(token)
        return _user_from_payload(payload)
    except jwt.PyJWTError:
        return None


OptionalUser = Depends(optional_user)
