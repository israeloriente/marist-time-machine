"""Current-user profile (graduation_year + class) for the Marist app."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..deps import CurrentUser, User

router = APIRouter(prefix="/me", tags=["me"])


class ProfileOut(BaseModel):
    user_id: UUID
    graduation_year: int
    class_letter: str
    created_at: str
    updated_at: str


class ProfileIn(BaseModel):
    graduation_year: int = Field(ge=1900, le=2100)
    class_letter: str = Field(pattern="^[A-Fa-f]$")


@router.get("/profile", response_model=ProfileOut | None)
async def get_profile(user: User = CurrentUser) -> ProfileOut | None:
    """Return current user's profile, or null if not filled yet."""
    row = await db.fetchrow(
        "select user_id, graduation_year, class_letter, created_at, updated_at "
        "from public.user_profiles where user_id = $1",
        UUID(user.id),
    )
    if not row:
        return None
    return ProfileOut(
        user_id=row["user_id"],
        graduation_year=row["graduation_year"],
        class_letter=row["class_letter"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


@router.put("/profile", response_model=ProfileOut)
async def upsert_profile(body: ProfileIn, user: User = CurrentUser) -> ProfileOut:
    """Create or update the current user's profile."""
    row = await db.fetchrow(
        """
        insert into public.user_profiles (user_id, graduation_year, class_letter)
        values ($1, $2, $3)
        on conflict (user_id) do update
          set graduation_year = excluded.graduation_year,
              class_letter    = excluded.class_letter,
              updated_at      = now()
        returning user_id, graduation_year, class_letter, created_at, updated_at
        """,
        UUID(user.id),
        body.graduation_year,
        body.class_letter.upper(),
    )
    assert row is not None
    return ProfileOut(
        user_id=row["user_id"],
        graduation_year=row["graduation_year"],
        class_letter=row["class_letter"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
    )


# Silence unused-import linter if datetime ever drops out
_ = datetime
