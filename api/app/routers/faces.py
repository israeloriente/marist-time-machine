"""Face-level admin operations."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from ..deps import CurrentUser, User
from ..services import storage as storage_svc

router = APIRouter(prefix="/faces", tags=["faces"])


class FaceOut(BaseModel):
    id: UUID
    photo_id: UUID
    bbox: list[float]
    detection_score: float
    person_id: UUID | None
    signed_url: str


class ReassignRequest(BaseModel):
    person_id: UUID | None


@router.get("/unassigned", response_model=list[FaceOut])
async def list_unassigned(
    limit: int = 100,
    offset: int = 0,
    min_score: float = 0.0,
    _user: User = CurrentUser,
) -> list[FaceOut]:
    """List faces that don't belong to any person yet."""
    rows = await db.fetch(
        """
        select f.id, f.photo_id, f.bbox, f.detection_score, f.person_id,
               p.storage_bucket, p.storage_path
        from public.faces f
        join public.photos p on p.id = f.photo_id
        where f.person_id is null
          and coalesce(f.detection_score, 0) >= $3
        order by f.detection_score desc nulls last
        limit $1 offset $2
        """,
        limit,
        offset,
        min_score,
    )
    return [
        FaceOut(
            id=r["id"],
            photo_id=r["photo_id"],
            bbox=r["bbox"],
            detection_score=float(r["detection_score"] or 0),
            person_id=r["person_id"],
            signed_url=storage_svc.signed_url(r["storage_bucket"], r["storage_path"]),
        )
        for r in rows
    ]


@router.patch("/{face_id}")
async def reassign_face(
    face_id: UUID,
    body: ReassignRequest,
    _user: User = CurrentUser,
) -> dict:
    """Move a face to a different person (or unset by passing null)."""
    if body.person_id is not None:
        exists = await db.fetchrow("select id from public.people where id = $1", body.person_id)
        if not exists:
            raise HTTPException(status_code=404, detail="person not found")

    result = await db.execute(
        "update public.faces set person_id = $1 where id = $2",
        body.person_id,
        face_id,
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="face not found")
    return {"ok": True, "face_id": str(face_id), "person_id": str(body.person_id) if body.person_id else None}


class CreatePersonFromFaceRequest(BaseModel):
    display_name: str | None = None


@router.post("/{face_id}/promote")
async def promote_face_to_person(
    face_id: UUID,
    body: CreatePersonFromFaceRequest,
    _user: User = CurrentUser,
) -> dict:
    """Create a new person seeded by this face (useful for unassigned faces).
    The face becomes the new person's thumbnail."""
    face = await db.fetchrow("select id from public.faces where id = $1", face_id)
    if not face:
        raise HTTPException(status_code=404, detail="face not found")

    new_person = await db.fetchrow(
        "insert into public.people (display_name, thumbnail_face_id) values ($1, $2) returning id",
        body.display_name,
        face_id,
    )
    assert new_person is not None
    person_id = new_person["id"]
    await db.execute(
        "update public.faces set person_id = $1 where id = $2",
        person_id,
        face_id,
    )
    return {"person_id": str(person_id), "face_id": str(face_id)}
