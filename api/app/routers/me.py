"""Current-user profile (graduation_year + class + terms acceptance)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..deps import CurrentUser, User

router = APIRouter(prefix="/me", tags=["me"])

# Current policy version. Bump this string when the terms text changes
# significantly — users with an older terms_version will be asked to
# re-accept (frontend gate).
TERMS_VERSION = "2026-05-19"


class ProfileOut(BaseModel):
    user_id: UUID
    graduation_year: int
    class_letter: str
    terms_accepted_at: str | None = None
    terms_version: str | None = None
    created_at: str
    updated_at: str


class ProfileIn(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    class_letter: str = Field(pattern="^[A-Fa-f]$")
    accept_terms: bool = False


def _row_to_profile(row) -> ProfileOut:
    return ProfileOut(
        user_id=row["user_id"],
        graduation_year=row["graduation_year"],
        class_letter=row["class_letter"],
        terms_accepted_at=(
            row["terms_accepted_at"].isoformat() if row["terms_accepted_at"] else None
        ),
        terms_version=row["terms_version"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


@router.get("/profile", response_model=ProfileOut | None)
async def get_profile(user: User = CurrentUser) -> ProfileOut | None:
    """Return current user's profile, or null if not filled yet."""
    row = await db.fetchrow(
        """
        select user_id, graduation_year, class_letter,
               terms_accepted_at, terms_version, created_at, updated_at
        from public.user_profiles where user_id = $1
        """,
        UUID(user.id),
    )
    return _row_to_profile(row) if row else None


@router.put("/profile", response_model=ProfileOut)
async def upsert_profile(body: ProfileIn, user: User = CurrentUser) -> ProfileOut:
    """Create or update the current user's profile.

    The user must accept the terms (accept_terms=True) on first creation.
    On subsequent updates we keep the previously-accepted version unless
    accept_terms=True is sent again (which re-stamps to the current version).
    """
    # Look up existing row to know whether we need to enforce terms.
    existing = await db.fetchrow(
        "select terms_accepted_at from public.user_profiles where user_id = $1",
        UUID(user.id),
    )

    if not existing and not body.accept_terms:
        raise HTTPException(
            status_code=400,
            detail="você precisa aceitar os termos de uso para criar o perfil",
        )

    if body.accept_terms:
        terms_set_sql = ", terms_accepted_at = now(), terms_version = $4"
        terms_params = [TERMS_VERSION]
    else:
        terms_set_sql = ""
        terms_params = []

    row = await db.fetchrow(
        f"""
        insert into public.user_profiles
          (user_id, graduation_year, class_letter, terms_accepted_at, terms_version)
        values ($1, $2, $3, {"now()" if body.accept_terms else "null"},
                {"$4" if body.accept_terms else "null"})
        on conflict (user_id) do update
          set graduation_year = excluded.graduation_year,
              class_letter    = excluded.class_letter,
              updated_at      = now()
              {terms_set_sql}
        returning user_id, graduation_year, class_letter,
                  terms_accepted_at, terms_version, created_at, updated_at
        """,
        UUID(user.id),
        body.graduation_year,
        body.class_letter.upper(),
        *terms_params,
    )
    assert row is not None
    return _row_to_profile(row)
