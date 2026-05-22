"""People: list, rename, merge, split."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .. import db
from .. import scheduler
from ..deps import CurrentUser, RequireAdmin, User
from ..services.clustering import recluster_all, stats as clustering_stats

router = APIRouter(prefix="/people", tags=["people"])


class PersonOut(BaseModel):
    id: UUID
    display_name: str | None
    thumbnail_face_id: UUID | None
    face_count: int
    status: str = "active"  # 'active' | 'rejected'
    # 'student' (graduation_year + class_letter) or 'collaborator' (entry/exit range)
    person_type: str = "student"
    # Canonical graduation info (admin/community-curated)
    graduation_year: int | None = None
    class_letter: str | None = None
    # Collaborator range (teacher/staff present from entry_year to exit_year)
    entry_year: int | None = None
    exit_year: int | None = None
    # Derived from photo metadata (fallback when canonical is null)
    graduation_years: list[int] = []
    classes: list[str] = []
    # Thumbnail face embedded so the list view doesn't need an extra
    # /people/{id}/faces round-trip per person. Null when no approved face.
    thumb_signed_url: str | None = None
    thumb_bbox: list[float] | None = None


class PersonUpdate(BaseModel):
    display_name: str | None = None
    is_hidden: bool | None = None  # deprecated; prefer status
    status: str | None = None  # 'active' | 'rejected'
    person_type: str | None = None  # 'student' | 'collaborator'
    graduation_year: int | None = None
    class_letter: str | None = None
    entry_year: int | None = None
    exit_year: int | None = None


class MergeRequest(BaseModel):
    source_id: UUID
    target_id: UUID


@router.get("", response_model=list[PersonOut])
async def list_people(
    limit: int = 500,
    offset: int = 0,
    year: int | None = None,
    klass: str | None = Query(None, alias="class"),
    status_filter: str = Query("active", alias="status"),
    _user: User = CurrentUser,
) -> list[PersonOut]:
    """List people with derived graduation_years + classes from their photos.

    Filters:
    - status: 'active' (default) or 'rejected' — rejected people are hidden
      from regular queries but admin can list them to reactivate.
    - year: only people who appear in at least one photo tagged with this year
    - klass: only people who appear in at least one photo of this class (A-F)
    """
    if status_filter not in {"active", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be active|rejected")
    params: list[object] = [status_filter]
    where_clauses = [f"p.status = $1"]

    if year is not None:
        params.append(year)
        i = len(params)
        # Year matching, in priority order:
        #  1. Student with a canonical graduation_year == the year.
        #  2. Collaborator whose entry..exit range covers the year. An open
        #     bound (null entry or null exit) is treated as "no limit on that
        #     side" so a half-filled range still matches.
        #  3. Person with no canonical year/range: fall back to the years of
        #     the photos they appear in.
        where_clauses.append(
            f"""(
              (p.person_type = 'student'
               and p.graduation_year is not null and p.graduation_year = ${i})
              or (
                p.person_type = 'collaborator'
                and (p.entry_year is not null or p.exit_year is not null)
                and ${i} >= coalesce(p.entry_year, ${i})
                and ${i} <= coalesce(p.exit_year, ${i})
              )
              or (
                p.graduation_year is null
                and not (p.person_type = 'collaborator'
                         and (p.entry_year is not null or p.exit_year is not null))
                and exists (
                  select 1
                  from public.faces f2
                  join public.photos ph2 on ph2.id = f2.photo_id
                  where f2.person_id = p.id
                    and ph2.metadata->>'graduation_year' ~ '^\\d+$'
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
        select p.id, p.display_name, p.thumbnail_face_id, p.status,
               p.person_type, p.graduation_year, p.class_letter,
               p.entry_year, p.exit_year,
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
               ) as classes,
               thumb.bbox as thumb_bbox,
               thumb.storage_bucket as thumb_bucket,
               thumb.storage_path as thumb_path,
               thumb.metadata as thumb_metadata
        from public.people p
        left join public.faces f on f.person_id = p.id
        left join public.photos ph on ph.id = f.photo_id
        -- Pick a single thumbnail face per person (approved photos only).
        -- Prefer the admin-pinned thumbnail_face_id; otherwise highest score,
        -- matching what the old per-person /faces call returned as fs[0].
        left join lateral (
          select tf.bbox, tp.storage_bucket, tp.storage_path, tp.metadata
          from public.faces tf
          join public.photos tp on tp.id = tf.photo_id
          where tf.person_id = p.id
            and tp.moderation_status = 'approved'
          order by (tf.id = p.thumbnail_face_id) desc,
                   tf.detection_score desc nulls last
          limit 1
        ) thumb on true
        where {' and '.join(where_clauses)}
        group by p.id, thumb.bbox, thumb.storage_bucket,
                 thumb.storage_path, thumb.metadata
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
    from ..services import storage as storage_svc
    from .faces import _coerce_bbox

    rows = await db.fetch(sql, *params)
    out: list[PersonOut] = []
    for r in rows:
        thumb_url = None
        thumb_bbox = None
        if r["thumb_path"] is not None:
            meta = storage_svc.coerce_metadata(r["thumb_metadata"])
            thumb_url = storage_svc.thumb_signed_url(
                meta, r["thumb_bucket"], r["thumb_path"]
            )
            thumb_bbox = _coerce_bbox(r["thumb_bbox"])
        out.append(
            PersonOut(
                id=r["id"],
                display_name=r["display_name"],
                thumbnail_face_id=r["thumbnail_face_id"],
                face_count=r["face_count"],
                status=r["status"],
                person_type=r["person_type"],
                graduation_year=r["graduation_year"],
                class_letter=r["class_letter"],
                entry_year=r["entry_year"],
                exit_year=r["exit_year"],
                graduation_years=sorted(r["graduation_years"]) if r["graduation_years"] else [],
                classes=sorted(r["classes"]) if r["classes"] else [],
                thumb_signed_url=thumb_url,
                thumb_bbox=thumb_bbox,
            )
        )
    return out


@router.get("/filters")
async def filters_available(_user: User = CurrentUser) -> dict:
    """Return the set of graduation_years and classes that exist in the DB.

    Used by the UI to populate filter dropdowns dynamically (so admin only
    sees options that actually have data).
    """
    # Years/classes come from two sources, unioned:
    #  - photo metadata (the upload-time hint), and
    #  - canonical people fields (student graduation_year, plus the bounds of
    #    collaborator entry/exit ranges) so years that only exist on a curated
    #    person still show up in the dropdowns.
    row = await db.fetchrow(
        """
        with photo_meta as (
          select
            array_remove(
              array_agg(distinct (metadata->>'graduation_year')::int)
                filter (where metadata ? 'graduation_year'
                        and metadata->>'graduation_year' ~ '^\\d+$'),
              null
            ) as years,
            array_remove(
              array_agg(distinct upper(metadata->>'class'))
                filter (where metadata ? 'class'
                        and metadata->>'class' <> ''),
              null
            ) as classes
          from public.photos
        ),
        people_meta as (
          select
            array_remove(array_agg(distinct y), null) as years,
            array_remove(array_agg(distinct class_letter), null) as classes
          from public.people p
          cross join lateral (
            values (p.graduation_year), (p.entry_year), (p.exit_year)
          ) as v(y)
          where p.status = 'active'
        )
        select
          coalesce(
            (select array_agg(distinct e) from unnest(
              coalesce(pm.years, '{}'::int[]) || coalesce(plm.years, '{}'::int[])
            ) e),
            '{}'::int[]
          ) as years,
          coalesce(
            (select array_agg(distinct e) from unnest(
              coalesce(pm.classes, '{}'::text[]) || coalesce(plm.classes, '{}'::text[])
            ) e),
            '{}'::text[]
          ) as classes
        from photo_meta pm cross join people_meta plm
        """
    )
    return {
        "years": sorted(row["years"] or []),
        "classes": sorted(row["classes"] or []),
    }


# IMPORTANT: keep all fixed-path routes (/stats, /merge, /recluster*) ABOVE
# the dynamic /{person_id} ones. FastAPI matches routes in declaration order,
# so a request to /people/stats would otherwise be parsed as person_id="stats"
# and blow up Pydantic's UUID parsing.

@router.get("/stats")
async def get_stats(_user: User = CurrentUser) -> dict:
    """Return how many faces are clustered, total, and how many people exist."""
    return await clustering_stats()


@router.post("/merge")
async def merge_people(body: MergeRequest, _user: User = RequireAdmin) -> dict:
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


@router.post("/recluster")
async def recluster(reset: bool = True, _user: User = RequireAdmin) -> dict:
    """Re-run DBSCAN globally. If reset=true, wipes existing clusters first."""
    return await recluster_all(reset=reset)


@router.get("/recluster/status")
async def recluster_status(_user: User = CurrentUser) -> dict:
    """Show last scheduled recluster result + next scheduled run."""
    return {
        "next_run_at": scheduler.next_run_iso(),
        "last": scheduler.last_result() or None,
    }


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: UUID, _user: User = CurrentUser) -> PersonOut:
    """Return a single person regardless of status — admin needs this to
    view a rejected person before reactivating."""
    row = await db.fetchrow(
        """
        select p.id, p.display_name, p.thumbnail_face_id, p.status,
               p.person_type, p.graduation_year, p.class_letter,
               p.entry_year, p.exit_year,
               (select count(*) from public.faces f where f.person_id = p.id) as face_count
        from public.people p where p.id = $1
        """,
        person_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut(**dict(row))


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: UUID, body: PersonUpdate, _user: User = RequireAdmin
) -> PersonOut:
    # Pydantic .model_fields_set tells us which keys the caller actually sent,
    # so passing display_name=null is distinct from omitting it.
    sent = body.model_fields_set
    fields: list[str] = []
    args: list = []
    set_cols: set[str] = set()

    def add(col: str, val):
        # First write wins. The type-switch block below runs before the explicit
        # field setters, so its intent (null the irrelevant side) takes priority
        # over a stray graduation_year sent alongside a switch to collaborator.
        if col in set_cols:
            return
        set_cols.add(col)
        args.append(val)
        fields.append(f"{col} = ${len(args)}")

    if "display_name" in sent:
        add("display_name", body.display_name)
    if "is_hidden" in sent and body.is_hidden is not None:
        # Legacy field — keep working but it maps onto status now.
        add("status", "rejected" if body.is_hidden else "active")
    if "status" in sent and body.status is not None:
        if body.status not in {"active", "rejected"}:
            raise HTTPException(
                status_code=400, detail="status must be active|rejected"
            )
        add("status", body.status)
    if "person_type" in sent and body.person_type is not None:
        if body.person_type not in {"student", "collaborator"}:
            raise HTTPException(
                status_code=400, detail="person_type must be student|collaborator"
            )
        add("person_type", body.person_type)
        # Switching type clears the other side's now-irrelevant fields so a
        # collaborator doesn't keep a stale class, nor a student a stale range.
        if body.person_type == "collaborator":
            add("graduation_year", None)
            add("class_letter", None)
        else:
            add("entry_year", None)
            add("exit_year", None)
    if "graduation_year" in sent:
        add("graduation_year", body.graduation_year)
    if "class_letter" in sent:
        add(
            "class_letter",
            body.class_letter.upper() if body.class_letter else None,
        )
    if "entry_year" in sent:
        add("entry_year", body.entry_year)
    if "exit_year" in sent:
        add("exit_year", body.exit_year)

    if not fields:
        raise HTTPException(status_code=400, detail="nothing to update")
    args.append(person_id)
    await db.execute(
        f"update public.people set {', '.join(fields)} where id = ${len(args)}",
        *args,
    )
    row = await db.fetchrow(
        """
        select p.id, p.display_name, p.thumbnail_face_id, p.status,
               p.person_type, p.graduation_year, p.class_letter,
               p.entry_year, p.exit_year,
               (select count(*) from public.faces f where f.person_id = p.id) as face_count
        from public.people p where p.id = $1
        """,
        person_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="person not found")
    return PersonOut(**dict(row))


@router.get("/{person_id}/photos")
async def person_photos(person_id: UUID, _user: User = CurrentUser) -> list[dict]:
    from ..services import storage as storage_svc
    rows = await db.fetch(
        """
        select distinct p.id, p.storage_bucket, p.storage_path, p.uploaded_at, p.metadata
        from public.photos p
        join public.faces f on f.photo_id = p.id
        where f.person_id = $1
          and p.moderation_status = 'approved'
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
          and p.moderation_status = 'approved'
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
