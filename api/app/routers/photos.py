"""Photos: ingestion + listing."""

from __future__ import annotations

import hashlib
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
    duplicate: bool = False  # true when the upload matched an existing photo by content hash
    moderation_status: str = "pending"  # pending | approved | rejected
    pending: bool = False                # convenience flag for the upload UI


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

    # 1. Dedupe check by content hash (SHA-256 of the raw bytes)
    content_hash = hashlib.sha256(payload).hexdigest()
    existing = await db.fetchrow(
        """
        select id, storage_path, storage_bucket, uploaded_at, metadata
        from public.photos
        where content_hash = $1
        limit 1
        """,
        content_hash,
    )
    if existing:
        return PhotoOut(
            id=existing["id"],
            storage_path=existing["storage_path"],
            storage_bucket=existing["storage_bucket"],
            uploaded_at=existing["uploaded_at"].isoformat(),
            metadata=existing["metadata"] if isinstance(existing["metadata"], dict) else {},
            faces=[],
            duplicate=True,
        )

    # 2. Persist original to Supabase Storage
    safe_name = file.filename or ("upload.mp4" if is_video else "upload.jpg")
    path = f"{user.id}/{safe_name}"
    storage.storage_client().storage.from_("photos").upload(
        path,
        payload,
        {"content-type": file.content_type or "application/octet-stream", "upsert": "true"},
    )

    # 3. Insert photo row (with content_hash)
    photo_row = await db.fetchrow(
        """
        insert into public.photos (storage_bucket, storage_path, original_filename, uploaded_by, metadata, content_hash)
        values ('photos', $1, $2, $3, $4, $5)
        returning id, storage_path, storage_bucket, uploaded_at, metadata
        """,
        path,
        safe_name,
        UUID(user.id),
        metadata,
        content_hash,
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

        # Persist the extracted frame as the video's thumbnail so the UI
        # can show it without re-running ffmpeg.
        try:
            thumb_path = f"{user.id}/.thumbs/{photo_id}.jpg"
            storage.storage_client().storage.from_("thumbnails").upload(
                thumb_path,
                frame_bytes,
                {"content-type": "image/jpeg", "upsert": "true"},
            )
            # Stamp the metadata so the UI knows where to find the thumb.
            new_meta = dict(photo_row["metadata"] or {})
            new_meta["thumb_bucket"] = "thumbnails"
            new_meta["thumb_path"] = thumb_path
            await db.execute(
                "update public.photos set metadata = $1 where id = $2",
                new_meta,
                photo_id,
            )
        except Exception:
            # Non-fatal: ML will still run, UI falls back to native <video>
            pass

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
            f["bbox"],
            f["landmarks"],
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
        moderation_status="pending",
        pending=True,
    )


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------

class PhotoModerationOut(BaseModel):
    id: UUID
    storage_bucket: str
    storage_path: str
    uploaded_at: str
    uploaded_by: UUID | None
    uploader_email: str | None
    metadata: dict
    media_type: str
    signed_url: str
    thumb_signed_url: str
    moderation_status: str
    moderation_note: str | None
    moderated_at: str | None
    face_count: int


@router.get("/moderation", response_model=list[PhotoModerationOut])
async def list_for_moderation(
    status_filter: str = "pending",
    limit: int = 100,
    offset: int = 0,
    _user: User = CurrentUser,
) -> list[PhotoModerationOut]:
    """Admin queue: list photos by moderation status (pending/approved/rejected)."""
    if status_filter not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be pending|approved|rejected")
    rows = await db.fetch(
        """
        select p.id, p.storage_bucket, p.storage_path, p.uploaded_at, p.uploaded_by,
               p.metadata, p.moderation_status, p.moderation_note, p.moderated_at,
               u.email as uploader_email,
               (select count(*) from public.faces f where f.photo_id = p.id) as face_count
        from public.photos p
        left join auth.users u on u.id = p.uploaded_by
        where p.moderation_status = $1
        order by p.uploaded_at desc
        limit $2 offset $3
        """,
        status_filter,
        limit,
        offset,
    )
    out: list[PhotoModerationOut] = []
    for r in rows:
        meta = storage.coerce_metadata(r["metadata"])
        out.append(PhotoModerationOut(
            id=r["id"],
            storage_bucket=r["storage_bucket"],
            storage_path=r["storage_path"],
            uploaded_at=r["uploaded_at"].isoformat(),
            uploaded_by=r["uploaded_by"],
            uploader_email=r["uploader_email"],
            metadata=meta,
            media_type=meta.get("media_type", "image"),
            signed_url=storage.signed_url(r["storage_bucket"], r["storage_path"]),
            thumb_signed_url=storage.thumb_signed_url(meta, r["storage_bucket"], r["storage_path"]),
            moderation_status=r["moderation_status"],
            moderation_note=r["moderation_note"],
            moderated_at=r["moderated_at"].isoformat() if r["moderated_at"] else None,
            face_count=r["face_count"],
        ))
    return out


@router.get("/moderation/counts")
async def moderation_counts(_user: User = CurrentUser) -> dict:
    row = await db.fetchrow(
        """
        select
          count(*) filter (where moderation_status = 'pending')  as pending,
          count(*) filter (where moderation_status = 'approved') as approved,
          count(*) filter (where moderation_status = 'rejected') as rejected
        from public.photos
        """
    )
    return dict(row) if row else {"pending": 0, "approved": 0, "rejected": 0}


class ModerationDecision(BaseModel):
    note: str | None = None


@router.post("/{photo_id}/approve", response_model=PhotoModerationOut)
async def approve_photo(
    photo_id: UUID, body: ModerationDecision | None = None, user: User = CurrentUser
) -> PhotoModerationOut:
    return await _set_moderation(photo_id, "approved", body, user)


@router.post("/{photo_id}/reject", response_model=PhotoModerationOut)
async def reject_photo(
    photo_id: UUID, body: ModerationDecision | None = None, user: User = CurrentUser
) -> PhotoModerationOut:
    return await _set_moderation(photo_id, "rejected", body, user)


async def _set_moderation(
    photo_id: UUID, status_str: str, body: ModerationDecision | None, user: User,
) -> PhotoModerationOut:
    note = (body.note.strip() if body and body.note else None) or None
    result = await db.execute(
        """
        update public.photos
           set moderation_status = $1,
               moderation_note = $2,
               moderated_at = now(),
               moderated_by = $3
         where id = $4
        """,
        status_str,
        note,
        UUID(user.id),
        photo_id,
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="photo not found")

    row = await db.fetchrow(
        """
        select p.id, p.storage_bucket, p.storage_path, p.uploaded_at, p.uploaded_by,
               p.metadata, p.moderation_status, p.moderation_note, p.moderated_at,
               u.email as uploader_email,
               (select count(*) from public.faces f where f.photo_id = p.id) as face_count
        from public.photos p
        left join auth.users u on u.id = p.uploaded_by
        where p.id = $1
        """,
        photo_id,
    )
    assert row is not None
    meta = storage.coerce_metadata(row["metadata"])
    return PhotoModerationOut(
        id=row["id"],
        storage_bucket=row["storage_bucket"],
        storage_path=row["storage_path"],
        uploaded_at=row["uploaded_at"].isoformat(),
        uploaded_by=row["uploaded_by"],
        uploader_email=row["uploader_email"],
        metadata=meta,
        media_type=meta.get("media_type", "image"),
        signed_url=storage.signed_url(row["storage_bucket"], row["storage_path"]),
        thumb_signed_url=storage.thumb_signed_url(meta, row["storage_bucket"], row["storage_path"]),
        moderation_status=row["moderation_status"],
        moderation_note=row["moderation_note"],
        moderated_at=row["moderated_at"].isoformat() if row["moderated_at"] else None,
        face_count=row["face_count"],
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


@router.post("/regenerate-thumbnails")
async def regenerate_thumbnails(_user: User = CurrentUser) -> dict:
    """Generate missing thumbnails for legacy videos.

    Walks every photo with metadata.media_type=='video' that doesn't already
    have metadata.thumb_path. Downloads the original, extracts a JPEG frame
    via ffmpeg, uploads to the 'thumbnails' bucket, and stamps the metadata.
    """
    rows = await db.fetch(
        """
        select id, storage_bucket, storage_path, uploaded_by, metadata
        from public.photos
        where metadata->>'media_type' = 'video'
          and (metadata->>'thumb_path' is null or metadata->>'thumb_path' = '')
        order by uploaded_at asc
        """,
    )

    generated = 0
    errors = 0

    for r in rows:
        try:
            data = storage.download(r["storage_bucket"], r["storage_path"])
            frame = await video.extract_thumbnail(data)

            owner = r["uploaded_by"]
            owner_str = str(owner) if owner else "system"
            thumb_path = f"{owner_str}/.thumbs/{r['id']}.jpg"

            storage.storage_client().storage.from_("thumbnails").upload(
                thumb_path,
                frame,
                {"content-type": "image/jpeg", "upsert": "true"},
            )

            new_meta = dict(r["metadata"] or {})
            new_meta["thumb_bucket"] = "thumbnails"
            new_meta["thumb_path"] = thumb_path
            await db.execute(
                "update public.photos set metadata = $1 where id = $2",
                new_meta,
                r["id"],
            )
            generated += 1
        except Exception:
            errors += 1

    return {
        "videos_visited": len(rows),
        "thumbnails_generated": generated,
        "errors": errors,
    }


@router.post("/dedupe")
async def dedupe(_user: User = CurrentUser) -> dict:
    """Backfill content_hash for legacy photos and remove duplicates.

    For each photo without content_hash: download its bytes from storage,
    compute SHA-256, set the hash. If another photo already has that hash,
    move faces to the survivor and delete the duplicate row (storage object
    is kept; safe to garbage-collect later).
    """
    rows = await db.fetch(
        """
        select id, storage_bucket, storage_path
        from public.photos
        where content_hash is null
        order by uploaded_at asc
        """,
    )

    hashed = 0
    duplicates_removed = 0
    errors = 0

    for r in rows:
        try:
            data = storage.download(r["storage_bucket"], r["storage_path"])
            h = hashlib.sha256(data).hexdigest()

            # Is there another row with this hash already?
            existing = await db.fetchrow(
                "select id from public.photos where content_hash = $1 limit 1",
                h,
            )
            if existing:
                # Reassign faces to the survivor and delete this row
                await db.execute(
                    "update public.faces set photo_id = $1 where photo_id = $2",
                    existing["id"],
                    r["id"],
                )
                await db.execute("delete from public.photos where id = $1", r["id"])
                duplicates_removed += 1
            else:
                await db.execute(
                    "update public.photos set content_hash = $1 where id = $2",
                    h,
                    r["id"],
                )
                hashed += 1
        except Exception:
            errors += 1

    return {
        "photos_visited": len(rows),
        "hashed": hashed,
        "duplicates_removed": duplicates_removed,
        "errors": errors,
    }


@router.get("/random")
async def random_photos(
    limit: int = 30,
    year: int | None = None,
) -> list[dict]:
    """Return random *image* photos (skip videos) for ambient slideshows."""
    where = [
        "coalesce(metadata->>'media_type','image') = 'image'",
        "moderation_status = 'approved'",
    ]
    params: list = []
    if year is not None:
        params.append(year)
        where.append(f"(metadata->>'graduation_year')::int = ${len(params)}")
    params.append(limit)
    rows = await db.fetch(
        f"""
        select id, storage_bucket, storage_path, metadata
        from public.photos
        where {' and '.join(where)}
        order by random()
        limit ${len(params)}
        """,
        *params,
    )
    out = []
    for r in rows:
        meta = storage.coerce_metadata(r["metadata"])
        out.append({
            "id": str(r["id"]),
            "signed_url": storage.signed_url(r["storage_bucket"], r["storage_path"]),
            "thumb_signed_url": storage.thumb_signed_url(meta, r["storage_bucket"], r["storage_path"]),
        })
    return out


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
