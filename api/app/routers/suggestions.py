"""Crowd-sourced name suggestions.

Anyone logged in can suggest a name for a person or for an orphan face.
Admins (currently == any logged-in user, see deps.py) approve or reject.
Approval sets people.display_name and (for face targets) promotes the
face to a brand-new person.
"""

from __future__ import annotations

import unicodedata
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..deps import CurrentUser, User

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _normalize(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace. Used for grouping votes."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = " ".join(name.lower().split())
    return name


class CreateSuggestion(BaseModel):
    person_id: UUID | None = None
    face_id: UUID | None = None
    suggested_name: str = Field(min_length=2, max_length=200)


class SuggestionOut(BaseModel):
    id: UUID
    person_id: UUID | None
    face_id: UUID | None
    suggested_name: str
    normalized_name: str
    suggested_by: UUID | None
    status: str
    created_at: str


@router.post("", response_model=SuggestionOut)
async def create_suggestion(body: CreateSuggestion, user: User = CurrentUser) -> SuggestionOut:
    if (body.person_id is None) == (body.face_id is None):
        raise HTTPException(
            status_code=400,
            detail="provide exactly one of person_id or face_id",
        )

    if body.person_id:
        exists = await db.fetchrow("select id from public.people where id = $1", body.person_id)
        if not exists:
            raise HTTPException(status_code=404, detail="person not found")
    else:
        exists = await db.fetchrow("select id from public.faces where id = $1", body.face_id)
        if not exists:
            raise HTTPException(status_code=404, detail="face not found")

    name = body.suggested_name.strip()
    normalized = _normalize(name)

    try:
        row = await db.fetchrow(
            """
            insert into public.name_suggestions
              (person_id, face_id, suggested_name, normalized_name, suggested_by)
            values ($1, $2, $3, $4, $5)
            returning id, person_id, face_id, suggested_name, normalized_name,
                      suggested_by, status, created_at
            """,
            body.person_id,
            body.face_id,
            name,
            normalized,
            UUID(user.id),
        )
    except Exception as exc:
        # Unique violation = same user already suggested this name for this target.
        if "name_sugg_dedupe_idx" in str(exc):
            raise HTTPException(status_code=409, detail="you already suggested this name") from exc
        raise

    assert row is not None
    return SuggestionOut(
        id=row["id"],
        person_id=row["person_id"],
        face_id=row["face_id"],
        suggested_name=row["suggested_name"],
        normalized_name=row["normalized_name"],
        suggested_by=row["suggested_by"],
        status=row["status"],
        created_at=row["created_at"].isoformat(),
    )


class GroupedSuggestion(BaseModel):
    """A target (person or face) with one or more votes for the same normalized name."""
    person_id: UUID | None
    face_id: UUID | None
    suggested_name: str         # most recent raw name spelling
    normalized_name: str
    vote_count: int
    first_suggested_at: str
    last_suggested_at: str
    suggestion_ids: list[UUID]  # for the bulk approve/reject endpoints


@router.get("/pending", response_model=list[GroupedSuggestion])
async def list_pending(_user: User = CurrentUser) -> list[GroupedSuggestion]:
    """Admin view: pending suggestions grouped by (target, normalized_name)."""
    rows = await db.fetch(
        """
        select
          person_id,
          face_id,
          (array_agg(suggested_name order by created_at desc))[1] as suggested_name,
          normalized_name,
          count(*) as vote_count,
          min(created_at) as first_at,
          max(created_at) as last_at,
          array_agg(id) as ids
        from public.name_suggestions
        where status = 'pending'
        group by person_id, face_id, normalized_name
        order by vote_count desc, last_at desc
        """,
    )
    return [
        GroupedSuggestion(
            person_id=r["person_id"],
            face_id=r["face_id"],
            suggested_name=r["suggested_name"],
            normalized_name=r["normalized_name"],
            vote_count=r["vote_count"],
            first_suggested_at=r["first_at"].isoformat(),
            last_suggested_at=r["last_at"].isoformat(),
            suggestion_ids=[i for i in r["ids"]],
        )
        for r in rows
    ]


@router.get("/by-person/{person_id}", response_model=list[GroupedSuggestion])
async def list_for_person(person_id: UUID, _user: User = CurrentUser) -> list[GroupedSuggestion]:
    """Pending suggestions for one specific person."""
    rows = await db.fetch(
        """
        select
          person_id,
          face_id,
          (array_agg(suggested_name order by created_at desc))[1] as suggested_name,
          normalized_name,
          count(*) as vote_count,
          min(created_at) as first_at,
          max(created_at) as last_at,
          array_agg(id) as ids
        from public.name_suggestions
        where status = 'pending' and person_id = $1
        group by person_id, face_id, normalized_name
        order by vote_count desc, last_at desc
        """,
        person_id,
    )
    return [
        GroupedSuggestion(
            person_id=r["person_id"],
            face_id=r["face_id"],
            suggested_name=r["suggested_name"],
            normalized_name=r["normalized_name"],
            vote_count=r["vote_count"],
            first_suggested_at=r["first_at"].isoformat(),
            last_suggested_at=r["last_at"].isoformat(),
            suggestion_ids=[i for i in r["ids"]],
        )
        for r in rows
    ]


class ApproveRequest(BaseModel):
    # Optional override: admin can tweak spelling before approving.
    final_name: str | None = None


@router.post("/{suggestion_id}/approve")
async def approve(suggestion_id: UUID, body: ApproveRequest | None = None, user: User = CurrentUser) -> dict:
    """Approve a suggestion: write display_name on the person, or promote a face
    to a brand-new person with that name. All other pending suggestions for
    the same target with the same normalized_name are marked approved too."""
    sugg = await db.fetchrow(
        "select * from public.name_suggestions where id = $1",
        suggestion_id,
    )
    if not sugg:
        raise HTTPException(status_code=404, detail="suggestion not found")
    if sugg["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"already {sugg['status']}")

    final_name = (body.final_name.strip() if body and body.final_name else sugg["suggested_name"].strip())
    if not final_name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    person_id = sugg["person_id"]

    if person_id is None:
        # Target is a face — promote to a new person and assign.
        face_row = await db.fetchrow(
            "select id from public.faces where id = $1",
            sugg["face_id"],
        )
        if not face_row:
            raise HTTPException(status_code=404, detail="face not found")
        new_person = await db.fetchrow(
            "insert into public.people (display_name, thumbnail_face_id) values ($1, $2) returning id",
            final_name,
            sugg["face_id"],
        )
        assert new_person is not None
        person_id = new_person["id"]
        await db.execute(
            "update public.faces set person_id = $1 where id = $2",
            person_id,
            sugg["face_id"],
        )
    else:
        await db.execute(
            "update public.people set display_name = $1 where id = $2",
            final_name,
            person_id,
        )

    # Resolve this and all sibling suggestions (same target + same normalized_name).
    await db.execute(
        """
        update public.name_suggestions
           set status = 'approved',
               resolved_at = now(),
               resolved_by = $1
         where status = 'pending'
           and normalized_name = $2
           and ( (person_id = $3 and $3 is not null) or
                 (face_id   = $4 and $4 is not null) )
        """,
        UUID(user.id),
        sugg["normalized_name"],
        person_id if sugg["person_id"] is not None else None,
        sugg["face_id"],
    )

    return {"ok": True, "person_id": str(person_id), "final_name": final_name}


@router.post("/{suggestion_id}/reject")
async def reject(suggestion_id: UUID, user: User = CurrentUser) -> dict:
    """Reject all suggestions sharing the same target + normalized_name."""
    sugg = await db.fetchrow(
        "select * from public.name_suggestions where id = $1",
        suggestion_id,
    )
    if not sugg:
        raise HTTPException(status_code=404, detail="suggestion not found")
    if sugg["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"already {sugg['status']}")

    await db.execute(
        """
        update public.name_suggestions
           set status = 'rejected',
               resolved_at = now(),
               resolved_by = $1
         where status = 'pending'
           and normalized_name = $2
           and ( (person_id = $3 and $3 is not null) or
                 (face_id   = $4 and $4 is not null) )
        """,
        UUID(user.id),
        sugg["normalized_name"],
        sugg["person_id"],
        sugg["face_id"],
    )
    return {"ok": True}


class TargetSummary(BaseModel):
    """How many suggestions a contributor has already cast for a given target."""
    pending_count: int


@router.get("/count")
async def count_for_target(
    person_id: UUID | None = None,
    face_id: UUID | None = None,
    _user: User = CurrentUser,
) -> dict:
    """How many pending suggestions exist for this target (any user, any name)."""
    if (person_id is None) == (face_id is None):
        raise HTTPException(status_code=400, detail="provide exactly one of person_id or face_id")
    row = await db.fetchrow(
        """
        select count(*) as n
        from public.name_suggestions
        where status = 'pending'
          and ( (person_id = $1 and $1 is not null) or (face_id = $2 and $2 is not null) )
        """,
        person_id,
        face_id,
    )
    return {"pending": int(row["n"]) if row else 0}
