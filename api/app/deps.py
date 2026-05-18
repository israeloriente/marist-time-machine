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


def _extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    return token


def current_user(request: Request) -> User:
    token = _extract_token(request)
    try:
        payload = jwt.decode(
            token,
            settings().jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
        ) from exc

    return User(
        id=payload["sub"],
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )


CurrentUser = Depends(current_user)


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
        payload = jwt.decode(
            token,
            settings().jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return User(
            id=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
        )
    except jwt.PyJWTError:
        return None


OptionalUser = Depends(optional_user)
