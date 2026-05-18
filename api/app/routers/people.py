"""People: list, rename, merge, split."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import db
from .. import scheduler
from ..deps import CurrentUser, User
from ..services.clustering import recluster_all, stats as clustering_stats

router = APIRouter(prefix="/people", tags=["people"])


class PersonOut(BaseModel):
    id: UUID
    display_name: str | None
    thumbnail_face_id: UUID | None
    face_count: int
    # Canonical graduation info (admin/community-curated)
    graduation_year: int | None = None
    class_letter: str | None = None
    # Derived from photo metadata (fallback when canonical is null)
    graduation_years: list[int] = []
    classes: list[str] = []


class PersonUpdate(BaseModel):
    display_name: str | None = None
    is_hidden: bool | None = None
    graduation_year: int | None = None
    class_letter: str | None = None


class MergeRequest(BaseModel):
    source_id: UUID
    target_id: UUID


@router.get("", response_model=list[PersonOut])
async def list_people(
    limit: int = 500,
    offset: int = 0,
    year: int | None = None,
    klass: str | None = Query(None, alias="class"),
    _user: User = CurrentUser,
) -> list[PersonOut]:
    """List people with derived graduation_years + classes from their photos.

    Optional filters:
    - year: only people who appear in at least one photo tagged with this year
    - klass: only people who appear in at least one photo of this class (A-F)

    Filters are combinable (both must match within the same photo? No — the
    current schema doesn't pair year+class per photo strictly. We require
    each filter independently on any photo of the person.)
    """
    where_clauses = ["p.is_hidden = false"]
    params: list = []

    if year is not None:
        params.append(year)
        i = len(params)
        # Priority: canonical p.graduation_year if set; otherwise derive from photos.
        where_clauses.append(
            f"""(
              (p.graduation_year is not null and p.graduation_year = ${i})
              or (
                p.graduation_year is null and exists (
                  select 1
                  from public.faces f2
                  join public.photos ph2 on ph2.id = f2.photo_id
                  where f2.person_id = p.id
                    and (ph2.metadata->>'graduation_year')::int = ${i}
                )
              )
            )"""
        )

    if klass:
        params.append(klass.upper())
        i = len(params)
        where_clauses.append(
            f"""(
              (p.class_letter is not null and p.class_letter = ${i})
              or (
                p.class_letter is null and exists (
                  select 1
                  from public.faces f3
                  join public.photos ph3 on ph3.id = f3.photo_id
                  where f3.person_id = p.id
                    and upper(ph3.metadata->>'class') = ${i}
                )
              )
            )"""
        )

    params.append(limit)
    params.append(offset)
    sql = f"""
        select p.id, p.display_name, p.thumbnail_face_id,
               p.graduation_year, p.class_letter,
               count(distinct f.id) as face_count,
               coalesce(
                 array_remove(
                   array_agg(distinct (ph.metadata->>'graduation_year')::int)
                     filter (where ph.metadata ? 'graduation_year'
                             and ph.metadata->>'graduation_year' ~ '^\\d+$'),
                   null
                 ),
                 '{{}}'::int[]
               ) as graduation_years,
               coalesce(
                 array_remove(
                   array_agg(distinct upper(ph.metadata->>'class'))
                     filter (where ph.metadata ? 'class'
                             and ph.metadata->>'class' <> ''),
                   null
                 ),
                 '{{}}'::text[]
               ) as classes
        from public.people p
        left join public.faces f on f.person_id = p.id
        left join public.photos ph on ph.id = f.photo_id
        where {' and '.join(where_clauses)}
        group by p.id
        -- Named people first, alphabetical (PT-BR collation if available).
        -- Anonymous (NULL display_name) at the bottom, ordered by face count desc
        -- so the most-photographed unknowns surface first.
        order by
          p.display_name is null,
          p.display_name asc,
          count(distinct f.id) desc,
          p.created_at desc
        limit ${len(params) - 1} offset ${len(params)}
    """
    rows = await db.fetch(sql, *params)
    return [
        PersonOut(
            id=r["id"],
            display_name=r["display_name"],
            thumbnail_face_id=r["thumbnail_face_id"],
            face_count=r["face_count"],
            graduation_year=r["graduation_year"],
            class_letter=r["class_letter"],
            graduation_years=sorted(r["graduation_years"]) if r["graduation_years"] else [],
            classes=sorted(r["classes"]) if r["classes"] else [],
        )
        for r in rows
    ]


@router.get("/filters")
async def filters_available(_user: User = CurrentUser) -> dict:
    """Return the set of graduation_years and classes that exist in the DB.

    Used by the UI to populate filter dropdowns dynamically (so admin only
    sees options that actually have data).
    """
    row = await db.fetchrow(
        """
        select
          coalesce(
            array_remove(
              array_agg(distinct (metadata->>'graduation_year')::int)
                filter (where metadata ? 'graduation_year'
                        and metadata->>'graduation_year' ~ '^\\d+$'),
              null
            ),
            '{}'::int[]
          ) as years,
          coalesce(
            array_remove(
              array_agg(distinct upper(metadata->>'class'))
                filter (where metadata ? 'class'
                        and metadata->>'class' <> ''),
              null
            ),
            '{}'::text[]
          ) as classes
        from public.photos
        """
    )
    return {
        "years": sorted(row["years"] or []),
        "classes": sorted(row["classes"] or []),
    }


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: UUID, body: PersonUpdate, _user: User = CurrentUser
) -> PersonOut:
    # Pydantic .model_fields_set tells us which keys the caller actually sent,
    # so passing display_name=null is distinct from omitting it.
    sent = body.model_fields_set
    fields: list[str] = []
    args: list = []

    def add(col: str, val):
        args.append(val)
        fields.append(f"{col} = ${len(args)}")

    if "display_name" in sent:
        add("display_name", body.display_name)
    if "is_hidden" in sent and body.is_hidden is not None:
        add("is_hidden", body.is_hidden)
    if "graduation_year" in sent:
        add("graduation_year", body.graduation_year)
    if "class_letter" in sent:
        add(
            "class_letter",
            body.class_letter.upper() if body.class_letter else None,
        )

    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    args.append(person_id)
    await db.execute(
        f"update public.people set {', '.join(fields)} where id = ${len(args)}",
        *args,
    )
    row = await db.fetchrow(
        """
        select p.id, p.display_name, p.thumbnail_face_id,
               p.graduation_year, p.class_letter,
               (select count(*) from public.faces f where f.person_id = p.id) as face_count
        from public.people p where p.id = $1
        """,
        person_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut(**dict(row))


@router.post("/merge")
async def merge_people(body: MergeRequest, _user: User = CurrentUser) -> dict:
    """Reassign all faces from source to target, then delete source."""
    if body.source_id == body.target_id:
        raise HTTPException(status_code=400, detail="source and target must differ")
    await db.execute(
        "update public.faces set person_id = $1 where person_id = $2",
        body.target_id,
        body.source_id,
    )
    await db.execute("delete from public.people where id = $1", body.source_id)
    return {"ok": True}


@router.get("/stats")
async def get_stats(_user: User = CurrentUser) -> dict:
    """Return how many faces are clustered, total, and how many people exist."""
    return await clustering_stats()


@router.post("/recluster")
async def recluster(reset: bool = True, _user: User = CurrentUser) -> dict:
    """Re-run DBSCAN globally. If reset=true, wipes existing clusters first."""
    return await recluster_all(reset=reset)


@router.get("/recluster/status")
async def recluster_status(_user: User = CurrentUser) -> dict:
    """Show last scheduled recluster result + next scheduled run."""
    return {
        "next_run_at": scheduler.next_run_iso(),
        "last": scheduler.last_result() or None,
    }


@router.get("/{person_id}/photos")
async def person_photos(person_id: UUID, _user: User = CurrentUser) -> list[dict]:
    from ..services import storage as storage_svc
    rows = await db.fetch(
        """
        select distinct p.id, p.storage_bucket, p.storage_path, p.uploaded_at, p.metadata
        from public.photos p
        join public.faces f on f.photo_id = p.id
        where f.person_id = $1
        order by p.uploaded_at desc
        """,
        person_id,
    )
    out = []
    for r in rows:
        meta = storage_svc.coerce_metadata(r["metadata"])
        out.append({
            "id": str(r["id"]),
            "storage_bucket": r["storage_bucket"],
            "storage_path": r["storage_path"],
            "uploaded_at": r["uploaded_at"].isoformat(),
            "metadata": meta,
            "media_type": meta.get("media_type", "image"),
            "signed_url": storage_svc.signed_url(r["storage_bucket"], r["storage_path"]),
            "thumb_signed_url": storage_svc.thumb_signed_url(meta, r["storage_bucket"], r["storage_path"]),
        })
    return out


@router.get("/{person_id}/faces")
async def person_faces(person_id: UUID, _user: User = CurrentUser) -> list[dict]:
    """List all faces assigned to this person with bbox + parent photo URL.

    For faces from videos, signed_url points to the thumbnail JPEG so that
    FaceThumb's canvas can crop the bbox region. Returning the .mp4 here
    would make FaceThumb fail silently because <img> can't load video.
    """
    from ..services import storage as storage_svc
    from .faces import _coerce_bbox
    rows = await db.fetch(
        """
        select f.id, f.bbox, f.detection_score, p.id as photo_id,
               p.storage_bucket, p.storage_path, p.metadata
        from public.faces f
        join public.photos p on p.id = f.photo_id
        where f.person_id = $1
        order by f.detection_score desc nulls last
        """,
        person_id,
    )
    out = []
    for r in rows:
        meta = storage_svc.coerce_metadata(r["metadata"])
        out.append({
            "id": str(r["id"]),
            "photo_id": str(r["photo_id"]),
            "bbox": _coerce_bbox(r["bbox"]),
            "detection_score": float(r["detection_score"] or 0),
            "signed_url": storage_svc.thumb_signed_url(meta, r["storage_bucket"], r["storage_path"]),
        })
    return out
