"""People: list, rename, merge, split."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..deps import CurrentUser, User
from ..services.clustering import recluster_all, stats as clustering_stats

router = APIRouter(prefix="/people", tags=["people"])


class PersonOut(BaseModel):
    id: UUID
    display_name: str | None
    thumbnail_face_id: UUID | None
    face_count: int


class PersonUpdate(BaseModel):
    display_name: str | None = None
    is_hidden: bool | None = None


class MergeRequest(BaseModel):
    source_id: UUID
    target_id: UUID


@router.get("", response_model=list[PersonOut])
async def list_people(limit: int = 100, offset: int = 0, _user: User = CurrentUser) -> list[PersonOut]:
    rows = await db.fetch(
        """
        select p.id, p.display_name, p.thumbnail_face_id,
               count(f.id) as face_count
        from public.people p
        left join public.faces f on f.person_id = p.id
        where p.is_hidden = false
        group by p.id
        order by face_count desc, p.created_at desc
        limit $1 offset $2
        """,
        limit,
        offset,
    )
    return [PersonOut(**dict(r)) for r in rows]


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(person_id: UUID, body: PersonUpdate, _user: User = CurrentUser) -> PersonOut:
    fields: list[str] = []
    args: list = []
    if body.display_name is not None:
        args.append(body.display_name)
        fields.append(f"display_name = ${len(args)}")
    if body.is_hidden is not None:
        args.append(body.is_hidden)
        fields.append(f"is_hidden = ${len(args)}")
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


@router.get("/{person_id}/photos")
async def person_photos(person_id: UUID, _user: User = CurrentUser) -> list[dict]:
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
    return [
        {
            "id": str(r["id"]),
            "storage_bucket": r["storage_bucket"],
            "storage_path": r["storage_path"],
            "uploaded_at": r["uploaded_at"].isoformat(),
            "metadata": r["metadata"],
        }
        for r in rows
    ]
