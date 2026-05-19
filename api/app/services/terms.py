"""Helpers to enforce that a user has accepted the current terms of use."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from .. import db
from ..deps import User


async def require_terms_accepted(user: User) -> None:
    """Raise 412 if the user hasn't accepted the terms.

    Called from endpoints that store or query personal data: photo upload,
    selfie search, name suggestions, etc. The frontend should intercept
    412 and bounce the user to /onboarding to accept.
    """
    row = await db.fetchrow(
        "select terms_accepted_at from public.user_profiles where user_id = $1",
        UUID(user.id),
    )
    if not row or row["terms_accepted_at"] is None:
        raise HTTPException(
            status_code=412,
            detail="você precisa aceitar os termos de uso antes de continuar",
        )
