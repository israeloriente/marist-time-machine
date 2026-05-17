"""Photos: ingestion + listing."""

from __future__ import annotations

import json
from uuid import UUID

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db
from ..deps import CurrentUser, User
from ..services import storage, video
from ..services.clustering import assign_face_to_person
from ..services.ml_client import ml_client

router = APIRouter(prefix="/photos", tags=["photos"])


class FaceOut(BaseModel):
    id: UUID
    person_id: UUID | None
    bbox: list[float]
    detection_score: float


class PhotoOut(BaseModel):
    id: UUID
    storage_path: str
    storage_bucket: str
    uploaded_at: str
    metadata: dict
    faces: list[FaceOut] = []


@router.post("", response_model=PhotoOut)
async def upload_photo(
    file: UploadFile = File(...),
    metadata_json: str = Form("{}"),
    user: User = CurrentUser,
) -> PhotoOut:
    """Upload an image or video to storage, run face analysis, persist faces, cluster.

    Videos: a single representative frame is extracted via ffmpeg (mirrors Immich).
    """
    ctype = (file.content_type or "").lower()
    is_video = ctype.startswith("video/")
    is_image = ctype.startswith("image/")
    if not (is_image or is_video):
        raise HTTPException(status_code=415, detail="must be an image or video")

    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid metadata_json: {exc}") from exc

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="empty file")

    metadata["media_type"] = "video" if is_video else "image"

    # 1. Persist original to Supabase Storage
    safe_name = file.filename or ("upload.mp4" if is_video else "upload.jpg")
    path = f"{user.id}/{safe_name}"
    storage.storage_client().storage.from_("photos").upload(
        path,
        payload,
        {"content-type": file.content_type or "application/octet-stream", "upsert": "true"},
    )

    # 2. Insert photo row
    photo_row = await db.fetchrow(
        """
        insert into public.photos (storage_bucket, storage_path, original_filename, uploaded_by, metadata)
        values ('photos', $1, $2, $3, $4)
        returning id, storage_path, storage_bucket, uploaded_at, metadata
        """,
        path,
        safe_name,
        UUID(user.id),
        json.dumps(metadata),
    )
    assert photo_row is not None
    photo_id = photo_row["id"]

    # 3. For videos, extract a thumbnail frame first; then detect + embed
    frame_bytes = payload
    if is_video:
        try:
            frame_bytes = await video.extract_thumbnail(payload)
        except Exception as exc:
            await db.execute(
                "update public.photos set processing_error = $1 where id = $2",
                f"thumbnail extraction failed: {exc}",
                photo_id,
            )
            return PhotoOut(
                id=photo_id,
                storage_path=photo_row["storage_path"],
                storage_bucket=photo_row["storage_bucket"],
                uploaded_at=photo_row["uploaded_at"].isoformat(),
                metadata=photo_row["metadata"],
                faces=[],
            )
    faces = await ml_client().analyze(frame_bytes, safe_name)

    inserted_faces: list[FaceOut] = []
    for f in faces:
        emb = np.array(f["embedding"], dtype=np.float32)
        face_row = await db.fetchrow(
            """
            insert into public.faces (photo_id, bbox, landmarks, detection_score, embedding)
            values ($1, $2, $3, $4, $5)
            returning id
            """,
            photo_id,
            json.dumps(f["bbox"]),
            json.dumps(f["landmarks"]),
            f["detection_score"],
            emb,
        )
        assert face_row is not None
        face_id = face_row["id"]
        person_id = await assign_face_to_person(face_id, f["embedding"])
        inserted_faces.append(
            FaceOut(
                id=face_id,
                person_id=person_id,
                bbox=f["bbox"],
                detection_score=f["detection_score"],
            )
        )

    # 4. Mark processed
    await db.execute(
        "update public.photos set processed_at = now() where id = $1",
        photo_id,
    )

    return PhotoOut(
        id=photo_id,
        storage_path=photo_row["storage_path"],
        storage_bucket=photo_row["storage_bucket"],
        uploaded_at=photo_row["uploaded_at"].isoformat(),
        metadata=photo_row["metadata"],
        faces=inserted_faces,
    )


@router.get("", response_model=list[PhotoOut])
async def list_photos(limit: int = 50, offset: int = 0, _user: User = CurrentUser) -> list[PhotoOut]:
    rows = await db.fetch(
        """
        select id, storage_path, storage_bucket, uploaded_at, metadata
        from public.photos
        order by uploaded_at desc
        limit $1 offset $2
        """,
        limit,
        offset,
    )
    return [
        PhotoOut(
            id=r["id"],
            storage_path=r["storage_path"],
            storage_bucket=r["storage_bucket"],
            uploaded_at=r["uploaded_at"].isoformat(),
            metadata=r["metadata"],
        )
        for r in rows
    ]


@router.get("/{photo_id}/url")
async def photo_signed_url(photo_id: UUID, _user: User = CurrentUser) -> dict:
    row = await db.fetchrow(
        "select storage_bucket, storage_path from public.photos where id = $1",
        photo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="photo not found")
    url = storage.signed_url(row["storage_bucket"], row["storage_path"])
    return {"url": url}
