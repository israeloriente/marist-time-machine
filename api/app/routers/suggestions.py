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
from ..deps import CurrentUser, RequireAdmin, User

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _normalize(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace. Used for grouping votes."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = " ".join(name.lower().split())
    return name


def resolve_type_fields(
    person_type: str | None,
    *,
    graduation_year: int | None,
    class_letter: str | None,
    entry_year: int | None,
    exit_year: int | None,
) -> tuple[int | None, str | None, int | None, int | None]:
    """Single source of truth for which year/class/range fields a person type keeps.

    Students carry graduation_year + class_letter; collaborators carry an
    entry/exit range. The irrelevant side is always nulled so it can't leak.
    A null person_type is treated as a student (the table default).

    Returns (graduation_year, class_letter, entry_year, exit_year).
    """
    if person_type == "collaborator":
        return None, None, entry_year, exit_year
    return graduation_year, class_letter, None, None


class CreateSuggestion(BaseModel):
    person_id: UUID | None = None
    face_id: UUID | None = None
    suggested_name: str = Field(min_length=2, max_length=200)
    # Student fields
    suggested_graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    suggested_class_letter: str | None = Field(default=None, pattern="^[A-Fa-f]$")
    # Person type + collaborator range. Defaults to None (= treat as student
    # unless explicitly flagged) so older clients keep working unchanged.
    suggested_person_type: str | None = Field(default=None, pattern="^(student|collaborator)$")
    suggested_entry_year: int | None = Field(default=None, ge=1900, le=2100)
    suggested_exit_year: int | None = Field(default=None, ge=1900, le=2100)


class SuggestionOut(BaseModel):
    id: UUID
    person_id: UUID | None
    face_id: UUID | None
    suggested_name: str
    normalized_name: str
    suggested_graduation_year: int | None = None
    suggested_class_letter: str | None = None
    suggested_person_type: str | None = None
    suggested_entry_year: int | None = None
    suggested_exit_year: int | None = None
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

    klass = body.suggested_class_letter.upper() if body.suggested_class_letter else None
    # One rule for which fields a type keeps; the rest are nulled.
    grad_year, klass, entry_year, exit_year = resolve_type_fields(
        body.suggested_person_type,
        graduation_year=body.suggested_graduation_year,
        class_letter=klass,
        entry_year=body.suggested_entry_year,
        exit_year=body.suggested_exit_year,
    )
    try:
        row = await db.fetchrow(
            """
            insert into public.name_suggestions
              (person_id, face_id, suggested_name, normalized_name, suggested_by,
               suggested_graduation_year, suggested_class_letter,
               suggested_person_type, suggested_entry_year, suggested_exit_year)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            returning id, person_id, face_id, suggested_name, normalized_name,
                      suggested_graduation_year, suggested_class_letter,
                      suggested_person_type, suggested_entry_year, suggested_exit_year,
                      suggested_by, status, created_at
            """,
            body.person_id,
            body.face_id,
            name,
            normalized,
            UUID(user.id),
            grad_year,
            klass,
            body.suggested_person_type,
            entry_year,
            exit_year,
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
        suggested_graduation_year=row["suggested_graduation_year"],
        suggested_class_letter=row["suggested_class_letter"],
        suggested_person_type=row["suggested_person_type"],
        suggested_entry_year=row["suggested_entry_year"],
        suggested_exit_year=row["suggested_exit_year"],
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
    suggested_graduation_year: int | None = None
    suggested_class_letter: str | None = None
    suggested_person_type: str | None = None
    suggested_entry_year: int | None = None
    suggested_exit_year: int | None = None
    vote_count: int
    first_suggested_at: str
    last_suggested_at: str
    suggestion_ids: list[UUID]  # for the bulk approve/reject endpoints


@router.get("/pending", response_model=list[GroupedSuggestion])
async def list_pending(_user: User = RequireAdmin) -> list[GroupedSuggestion]:
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


class NameVote(BaseModel):
    suggestion_id: UUID  # representative id (use this to approve/reject the group)
    suggested_name: str
    normalized_name: str
    suggested_graduation_year: int | None = None
    suggested_class_letter: str | None = None
    suggested_person_type: str | None = None
    suggested_entry_year: int | None = None
    suggested_exit_year: int | None = None
    vote_count: int
    first_at: str
    last_at: str


class TargetWithSuggestions(BaseModel):
    """One target (person or orphan face) with all its proposed names inside."""
    person_id: UUID | None
    face_id: UUID | None
    face_count: int = 0          # photos this person appears in, if person
    detection_score: float = 0.0 # face score, if orphan face
    thumb_signed_url: str | None = None
    thumb_bbox: list[float] | None = None
    names: list[NameVote]


@router.get("/pending/by-target", response_model=list[TargetWithSuggestions])
async def list_pending_by_target(_user: User = RequireAdmin) -> list[TargetWithSuggestions]:
    """Like /pending but groups by (person_id, face_id) — multiple name votes
    for the same target are nested inside a single result entry.

    Also pre-resolves a face thumbnail (signed URL + bbox) so the UI doesn't
    need a second round-trip per target.
    """
    from ..routers.faces import _coerce_bbox
    from ..services import storage as storage_svc

    rows = await db.fetch(
        """
        with grouped as (
          select
            person_id,
            face_id,
            (array_agg(suggested_name order by created_at desc))[1] as suggested_name,
            normalized_name,
            (array_agg(suggested_graduation_year order by created_at desc)
              filter (where suggested_graduation_year is not null))[1]
              as suggested_graduation_year,
            (array_agg(suggested_class_letter order by created_at desc)
              filter (where suggested_class_letter is not null))[1]
              as suggested_class_letter,
            (array_agg(suggested_person_type order by created_at desc)
              filter (where suggested_person_type is not null))[1]
              as suggested_person_type,
            (array_agg(suggested_entry_year order by created_at desc)
              filter (where suggested_entry_year is not null))[1]
              as suggested_entry_year,
            (array_agg(suggested_exit_year order by created_at desc)
              filter (where suggested_exit_year is not null))[1]
              as suggested_exit_year,
            count(*) as vote_count,
            min(created_at) as first_at,
            max(created_at) as last_at,
            (array_agg(id order by created_at desc))[1] as representative_id
          from public.name_suggestions
          where status = 'pending'
          group by person_id, face_id, normalized_name
        )
        select * from grouped
        order by vote_count desc, last_at desc
        """,
    )

    # Bucket name votes by (person_id, face_id)
    by_target: dict[tuple[str | None, str | None], list[NameVote]] = {}
    target_order: list[tuple[str | None, str | None]] = []
    for r in rows:
        key = (str(r["person_id"]) if r["person_id"] else None,
               str(r["face_id"])   if r["face_id"]   else None)
        if key not in by_target:
            by_target[key] = []
            target_order.append(key)
        by_target[key].append(
            NameVote(
                suggestion_id=r["representative_id"],
                suggested_name=r["suggested_name"],
                normalized_name=r["normalized_name"],
                suggested_graduation_year=r["suggested_graduation_year"],
                suggested_class_letter=r["suggested_class_letter"],
                suggested_person_type=r["suggested_person_type"],
                suggested_entry_year=r["suggested_entry_year"],
                suggested_exit_year=r["suggested_exit_year"],
                vote_count=r["vote_count"],
                first_at=r["first_at"].isoformat(),
                last_at=r["last_at"].isoformat(),
            )
        )

    # Resolve thumbs in one pass
    person_ids = [k[0] for k in target_order if k[0]]
    face_ids   = [k[1] for k in target_order if k[1]]

    # For each person, get a representative face (highest detection_score).
    person_thumbs: dict[str, dict] = {}
    if person_ids:
        prows = await db.fetch(
            """
            select distinct on (f.person_id)
              f.person_id, f.bbox, p.storage_bucket, p.storage_path, p.metadata
            from public.faces f
            join public.photos p on p.id = f.photo_id
            where f.person_id = any($1::uuid[])
            order by f.person_id, f.detection_score desc nulls last
            """,
            person_ids,
        )
        for pr in prows:
            meta = storage_svc.coerce_metadata(pr["metadata"])
            person_thumbs[str(pr["person_id"])] = {
                "bbox": _coerce_bbox(pr["bbox"]),
                "url": storage_svc.thumb_signed_url(meta, pr["storage_bucket"], pr["storage_path"]),
            }

    # For each orphan face, get its bbox + photo
    face_thumbs: dict[str, dict] = {}
    face_scores: dict[str, float] = {}
    if face_ids:
        frows = await db.fetch(
            """
            select f.id, f.bbox, f.detection_score,
                   p.storage_bucket, p.storage_path, p.metadata
            from public.faces f
            join public.photos p on p.id = f.photo_id
            where f.id = any($1::uuid[])
            """,
            face_ids,
        )
        for fr in frows:
            meta = storage_svc.coerce_metadata(fr["metadata"])
            face_thumbs[str(fr["id"])] = {
                "bbox": _coerce_bbox(fr["bbox"]),
                "url": storage_svc.thumb_signed_url(meta, fr["storage_bucket"], fr["storage_path"]),
            }
            face_scores[str(fr["id"])] = float(fr["detection_score"] or 0)

    # Person face counts (optional — small cost extra)
    person_face_counts: dict[str, int] = {}
    if person_ids:
        crows = await db.fetch(
            "select person_id, count(*) as n from public.faces where person_id = any($1::uuid[]) group by person_id",
            person_ids,
        )
        for cr in crows:
            person_face_counts[str(cr["person_id"])] = int(cr["n"])

    out: list[TargetWithSuggestions] = []
    for (pid, fid) in target_order:
        thumb = person_thumbs.get(pid) if pid else face_thumbs.get(fid)
        out.append(TargetWithSuggestions(
            person_id=UUID(pid) if pid else None,
            face_id=UUID(fid) if fid else None,
            face_count=person_face_counts.get(pid, 0) if pid else 0,
            detection_score=face_scores.get(fid, 0.0) if fid else 0.0,
            thumb_signed_url=thumb["url"] if thumb else None,
            thumb_bbox=thumb["bbox"] if thumb else None,
            names=by_target[(pid, fid)],
        ))
    return out


@router.get("/by-person/{person_id}", response_model=list[GroupedSuggestion])
async def list_for_person(person_id: UUID, _user: User = RequireAdmin) -> list[GroupedSuggestion]:
    """Pending suggestions for one specific person."""
    rows = await db.fetch(
        """
        select
          person_id,
          face_id,
          (array_agg(suggested_name order by created_at desc))[1] as suggested_name,
          normalized_name,
          (array_agg(suggested_graduation_year order by created_at desc)
            filter (where suggested_graduation_year is not null))[1]
            as suggested_graduation_year,
          (array_agg(suggested_class_letter order by created_at desc)
            filter (where suggested_class_letter is not null))[1]
            as suggested_class_letter,
          (array_agg(suggested_person_type order by created_at desc)
            filter (where suggested_person_type is not null))[1]
            as suggested_person_type,
          (array_agg(suggested_entry_year order by created_at desc)
            filter (where suggested_entry_year is not null))[1]
            as suggested_entry_year,
          (array_agg(suggested_exit_year order by created_at desc)
            filter (where suggested_exit_year is not null))[1]
            as suggested_exit_year,
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
            suggested_graduation_year=r["suggested_graduation_year"],
            suggested_class_letter=r["suggested_class_letter"],
            suggested_person_type=r["suggested_person_type"],
            suggested_entry_year=r["suggested_entry_year"],
            suggested_exit_year=r["suggested_exit_year"],
            vote_count=r["vote_count"],
            first_suggested_at=r["first_at"].isoformat(),
            last_suggested_at=r["last_at"].isoformat(),
            suggestion_ids=[i for i in r["ids"]],
        )
        for r in rows
    ]


class ApproveRequest(BaseModel):
    # Optional overrides: admin can tweak before approving.
    final_name: str | None = None
    final_graduation_year: int | None = None
    final_class_letter: str | None = None
    final_person_type: str | None = Field(default=None, pattern="^(student|collaborator)$")
    final_entry_year: int | None = None
    final_exit_year: int | None = None


@router.post("/{suggestion_id}/approve")
async def approve(suggestion_id: UUID, body: ApproveRequest | None = None, user: User = RequireAdmin) -> dict:
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

    final_name = (
        body.final_name.strip() if body and body.final_name else sugg["suggested_name"].strip()
    )
    if not final_name:
        raise HTTPException(status_code=400, detail="name cannot be empty")

    # Resolve final ano/turma (admin override takes priority, then suggestion).
    final_year = (
        body.final_graduation_year
        if body and body.final_graduation_year is not None
        else sugg["suggested_graduation_year"]
    )
    final_class = (
        body.final_class_letter.upper()
        if body and body.final_class_letter
        else sugg["suggested_class_letter"]
    )
    # Resolve person type + collaborator range, then run everything through the
    # same rule used at suggestion-create time so the irrelevant side is nulled
    # exactly once, in one place.
    final_type = (
        body.final_person_type
        if body and body.final_person_type
        else sugg["suggested_person_type"]
    )
    final_entry = (
        body.final_entry_year
        if body and body.final_entry_year is not None
        else sugg["suggested_entry_year"]
    )
    final_exit = (
        body.final_exit_year
        if body and body.final_exit_year is not None
        else sugg["suggested_exit_year"]
    )
    final_year, final_class, final_entry, final_exit = resolve_type_fields(
        final_type,
        graduation_year=final_year,
        class_letter=final_class,
        entry_year=final_entry,
        exit_year=final_exit,
    )

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
            """
            insert into public.people (display_name, thumbnail_face_id,
                                       graduation_year, class_letter,
                                       person_type, entry_year, exit_year)
            values ($1, $2, $3, $4, coalesce($5, 'student'), $6, $7) returning id
            """,
            final_name,
            sugg["face_id"],
            final_year,
            final_class,
            final_type,
            final_entry,
            final_exit,
        )
        assert new_person is not None
        person_id = new_person["id"]
        await db.execute(
            "update public.faces set person_id = $1 where id = $2",
            person_id,
            sugg["face_id"],
        )
    else:
        # coalesce keeps existing values when an override is null — but on a
        # type *switch* the now-irrelevant side must be force-nulled (a person
        # flipped student->collaborator shouldn't keep their old class). The
        # clear flags fire only when an explicit final_type says which side
        # is irrelevant.
        clear_student = final_type == "collaborator"
        clear_collab = final_type == "student"
        await db.execute(
            """
            update public.people
               set display_name = $1,
                   graduation_year = case when $8 then null
                                         else coalesce($2, graduation_year) end,
                   class_letter    = case when $8 then null
                                         else coalesce($3, class_letter) end,
                   person_type     = coalesce($5, person_type),
                   entry_year      = case when $9 then null
                                         else coalesce($6, entry_year) end,
                   exit_year       = case when $9 then null
                                         else coalesce($7, exit_year) end
             where id = $4
            """,
            final_name,
            final_year,
            final_class,
            person_id,
            final_type,
            final_entry,
            final_exit,
            clear_student,
            clear_collab,
        )

    # 1) Approve siblings with same target + same normalized_name (people
    #    who suggested the same name independently).
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

    # 2) Auto-reject every other pending suggestion for the same target
    #    (competing names lose once one is approved).
    await db.execute(
        """
        update public.name_suggestions
           set status = 'rejected',
               resolved_at = now(),
               resolved_by = $1
         where status = 'pending'
           and ( (person_id = $2 and $2 is not null) or
                 (face_id   = $3 and $3 is not null) )
        """,
        UUID(user.id),
        person_id if sugg["person_id"] is not None else None,
        sugg["face_id"],
    )

    return {"ok": True, "person_id": str(person_id), "final_name": final_name}


@router.post("/{suggestion_id}/reject")
async def reject(suggestion_id: UUID, user: User = RequireAdmin) -> dict:
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


class CountBatchIn(BaseModel):
    """Targets to fetch pending-suggestion counts for, in two grouped queries."""

    person_ids: list[UUID] = Field(default_factory=list)
    face_ids: list[UUID] = Field(default_factory=list)


@router.post("/count/batch")
async def count_for_targets(
    body: CountBatchIn,
    _user: User = CurrentUser,
) -> dict:
    """Pending-suggestion counts for many targets at once.

    Collapses the per-target /count N+1 (the /contribute page used to fire one
    request per person and per face) into two grouped queries. Returns
    {"people": {id: n}, "faces": {id: n}} with an entry only for ids that have
    at least one pending suggestion; callers should default missing ids to 0.
    """
    people: dict[str, int] = {}
    faces: dict[str, int] = {}
    if body.person_ids:
        rows = await db.fetch(
            """
            select person_id, count(*) as n
            from public.name_suggestions
            where status = 'pending' and person_id = any($1::uuid[])
            group by person_id
            """,
            body.person_ids,
        )
        people = {str(r["person_id"]): int(r["n"]) for r in rows}
    if body.face_ids:
        rows = await db.fetch(
            """
            select face_id, count(*) as n
            from public.name_suggestions
            where status = 'pending' and face_id = any($1::uuid[])
            group by face_id
            """,
            body.face_ids,
        )
        faces = {str(r["face_id"]): int(r["n"]) for r in rows}
    return {"people": people, "faces": faces}
