"""Photos: ingestion + listing."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db
from ..deps import CurrentUser, RequireAdmin, User
from ..services import media, storage, video
from ..services.terms import require_terms_accepted
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
    await require_terms_accepted(user)
    ctype = (file.content_type or "").lower()
    is_video = ctype.startswith("video/")
    is_image = ctype.startswith("image/")
    if not (is_image or is_video):
        raise HTTPException(status_code=415, detail="must be an image or video")

    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid metadata_json: {exc}") from exc

    raw_payload = await file.read()
    if not raw_payload:
        raise HTTPException(status_code=400, detail="empty file")

    metadata["media_type"] = "video" if is_video else "image"
    original_size = len(raw_payload)

    # 1. Compress server-side BEFORE hashing. The hash represents what we
    #    actually store, so dedupe sees byte-identical re-uploads of the
    #    same compressed bytes (e.g. user uploads the same JPEG twice).
    upload_content_type = file.content_type or "application/octet-stream"
    upload_ext = ""
    if is_image:
        payload, upload_content_type, upload_ext = media.compress_image(raw_payload)
    elif is_video:
        payload, upload_content_type, upload_ext = await media.compress_video(raw_payload)
    else:
        payload = raw_payload

    metadata["original_size_bytes"] = original_size
    metadata["compressed_size_bytes"] = len(payload)

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

    # 2. Persist compressed bytes to Supabase Storage.
    safe_name = file.filename or ("upload.mp4" if is_video else "upload.jpg")
    if upload_ext:
        # Compression changed the encoding — swap the extension so the
        # stored object's name matches its actual bytes.
        root, _, _ = safe_name.rpartition(".")
        safe_name = (root or safe_name) + upload_ext
    # The original filename (kept in original_filename below) may contain
    # accents, exotic whitespace, or punctuation that Supabase Storage rejects
    # as an InvalidKey. Build the storage key from a sanitized variant. Prefix
    # with a slice of the content hash so two differently-named files that
    # sanitize to the same key (e.g. both all-CJK) can't overwrite each other.
    key_name = storage.sanitize_key_name(safe_name)
    path = f"{user.id}/{content_hash[:12]}-{key_name}"
    storage.storage_client().storage.from_("photos").upload(
        path,
        payload,
        {"content-type": upload_content_type, "upsert": "true"},
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

    # 3. Run face analysis.
    #    - Image: single analyze() call on the original bytes.
    #    - Video: sample frames at ~1 fps, detect on each, then cluster
    #      within the video so each real person becomes one row in faces
    #      (not one row per frame they appear in).
    thumb_frame_bytes: bytes | None = None
    try:
        if is_video:
            faces, thumb_frame_bytes = await video.analyze_video(
                payload,
                ml_client().analyze,
            )
        else:
            faces = await ml_client().analyze(payload, safe_name)
    except Exception as exc:
        await db.execute(
            "update public.photos set processing_error = $1 where id = $2",
            f"face analysis failed: {exc}",
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

    # For videos, persist the chosen thumbnail (best-face frame, or
    # fallback frame) so the UI can render without re-running ffmpeg.
    if is_video and thumb_frame_bytes:
        try:
            thumb_path = f"{user.id}/.thumbs/{photo_id}.jpg"
            storage.storage_client().storage.from_("thumbnails").upload(
                thumb_path,
                thumb_frame_bytes,
                {"content-type": "image/jpeg", "upsert": "true"},
            )
            new_meta = dict(photo_row["metadata"] or {})
            new_meta["thumb_bucket"] = "thumbnails"
            new_meta["thumb_path"] = thumb_path
            await db.execute(
                "update public.photos set metadata = $1 where id = $2",
                new_meta,
                photo_id,
            )
        except Exception:
            # Non-fatal: UI falls back to native <video>
            pass

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
    _user: User = RequireAdmin,
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
async def moderation_counts(_user: User = RequireAdmin) -> dict:
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
    photo_id: UUID, body: ModerationDecision | None = None, user: User = RequireAdmin
) -> PhotoModerationOut:
    return await _set_moderation(photo_id, "approved", body, user)


@router.post("/{photo_id}/reject", response_model=PhotoModerationOut)
async def reject_photo(
    photo_id: UUID, body: ModerationDecision | None = None, user: User = RequireAdmin
) -> PhotoModerationOut:
    return await _set_moderation(photo_id, "rejected", body, user)


class DeletePhotoResult(BaseModel):
    deleted: bool
    photo_id: UUID
    faces_removed: int
    objects_removed: list[str]


class BulkRequest(BaseModel):
    photo_ids: list[UUID]
    note: str | None = None


class BulkResult(BaseModel):
    succeeded: list[UUID]
    failed: list[dict]  # [{id, reason}]


@router.delete("/{photo_id}", response_model=DeletePhotoResult)
async def delete_photo_permanently(
    photo_id: UUID,
    require_rejected: bool = True,
    _user: User = RequireAdmin,
) -> DeletePhotoResult:
    """Permanently delete a photo: row, faces, and bucket objects.

    By default only rejected photos can be hard-deleted (safety rail).
    Pass ?require_rejected=false to bypass — useful only for admin scripts.
    """
    row = await db.fetchrow(
        """
        select id, storage_bucket, storage_path, metadata, moderation_status
        from public.photos
        where id = $1
        """,
        photo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="photo not found")

    if require_rejected and row["moderation_status"] != "rejected":
        raise HTTPException(
            status_code=409,
            detail="só fotos rejeitadas podem ser apagadas permanentemente; rejeite primeiro",
        )

    meta = storage.coerce_metadata(row["metadata"])

    # 1) Count faces that will cascade-delete (FK ON DELETE CASCADE)
    face_count_row = await db.fetchrow(
        "select count(*) as n from public.faces where photo_id = $1",
        photo_id,
    )
    faces_removed = int(face_count_row["n"]) if face_count_row else 0

    # 2) Build list of bucket objects to remove
    removed: list[str] = []
    main_bucket = row["storage_bucket"]
    main_path = row["storage_path"]
    storage.remove(main_bucket, [main_path])
    removed.append(f"{main_bucket}/{main_path}")

    thumb_bucket = meta.get("thumb_bucket")
    thumb_path = meta.get("thumb_path")
    if thumb_bucket and thumb_path:
        storage.remove(thumb_bucket, [thumb_path])
        removed.append(f"{thumb_bucket}/{thumb_path}")

    # 3) Delete the DB row (cascades to faces)
    await db.execute("delete from public.photos where id = $1", photo_id)

    return DeletePhotoResult(
        deleted=True,
        photo_id=photo_id,
        faces_removed=faces_removed,
        objects_removed=removed,
    )


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


@router.post("/moderation/bulk-approve", response_model=BulkResult)
async def bulk_approve(body: BulkRequest, user: User = RequireAdmin) -> BulkResult:
    return await _bulk_moderate(body, "approved", user)


@router.post("/moderation/bulk-reject", response_model=BulkResult)
async def bulk_reject(body: BulkRequest, user: User = RequireAdmin) -> BulkResult:
    return await _bulk_moderate(body, "rejected", user)


async def _bulk_moderate(body: BulkRequest, status_str: str, user: User) -> BulkResult:
    if not body.photo_ids:
        return BulkResult(succeeded=[], failed=[])
    note = (body.note.strip() if body.note else None) or None
    await db.execute(
        """
        update public.photos
           set moderation_status = $1,
               moderation_note   = $2,
               moderated_at      = now(),
               moderated_by      = $3
         where id = any($4::uuid[])
        """,
        status_str,
        note,
        UUID(user.id),
        body.photo_ids,
    )
    # We don't track per-row failures from a single UPDATE; treat all as ok.
    return BulkResult(succeeded=body.photo_ids, failed=[])


@router.post("/moderation/bulk-delete", response_model=BulkResult)
async def bulk_delete(body: BulkRequest, _user: User = RequireAdmin) -> BulkResult:
    """Permanently delete a list of REJECTED photos (DB + Hetzner objects)."""
    if not body.photo_ids:
        return BulkResult(succeeded=[], failed=[])

    rows = await db.fetch(
        """
        select id, storage_bucket, storage_path, metadata, moderation_status
        from public.photos
        where id = any($1::uuid[])
        """,
        body.photo_ids,
    )

    succeeded: list[UUID] = []
    failed: list[dict] = []

    # Group bucket deletes for fewer round-trips
    deletes_by_bucket: dict[str, list[str]] = {}
    to_delete_ids: list[UUID] = []

    for r in rows:
        if r["moderation_status"] != "rejected":
            failed.append({"id": str(r["id"]), "reason": "não está rejeitada"})
            continue
        deletes_by_bucket.setdefault(r["storage_bucket"], []).append(r["storage_path"])
        meta = storage.coerce_metadata(r["metadata"])
        tb, tp = meta.get("thumb_bucket"), meta.get("thumb_path")
        if tb and tp:
            deletes_by_bucket.setdefault(tb, []).append(tp)
        to_delete_ids.append(r["id"])
        succeeded.append(r["id"])

    for bucket, paths in deletes_by_bucket.items():
        storage.remove(bucket, paths)

    if to_delete_ids:
        await db.execute(
            "delete from public.photos where id = any($1::uuid[])",
            to_delete_ids,
        )

    # Any ID the caller sent that we didn't find at all
    found_ids = {r["id"] for r in rows}
    for pid in body.photo_ids:
        if pid not in found_ids:
            failed.append({"id": str(pid), "reason": "não encontrada"})

    return BulkResult(succeeded=succeeded, failed=failed)


@router.get("/stats/public")
async def public_stats() -> dict:
    """Acervo-wide counts for the public home/hero. No auth.

    - photos: approved image+video count
    - people: named people (display_name not null) that aren't rejected
    - years: number of distinct graduation_years represented
    - oldest_year: smallest graduation_year (helps the copy "desde XX")
    """
    row = await db.fetchrow(
        """
        with approved_photos as (
          select id, metadata
          from public.photos
          where moderation_status = 'approved'
        )
        select
          (select count(*) from approved_photos) as photos,
          (select count(*) from public.people
             where display_name is not null
               and status = 'active') as named_people,
          (select count(distinct (metadata->>'graduation_year')::int)
             from approved_photos
             where metadata ? 'graduation_year'
               and metadata->>'graduation_year' ~ '^\\d+$') as years,
          (select min((metadata->>'graduation_year')::int)
             from approved_photos
             where metadata ? 'graduation_year'
               and metadata->>'graduation_year' ~ '^\\d+$') as oldest_year
        """
    )
    return {
        "photos": int(row["photos"]) if row else 0,
        "named_people": int(row["named_people"]) if row else 0,
        "years": int(row["years"]) if row else 0,
        "oldest_year": row["oldest_year"] if row else None,
    }


@router.get("", response_model=list[PhotoOut])
async def list_photos(limit: int = 50, offset: int = 0, _user: User = RequireAdmin) -> list[PhotoOut]:
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
async def regenerate_thumbnails(_user: User = RequireAdmin) -> dict:
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
async def dedupe(_user: User = RequireAdmin) -> dict:
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
        "coalesce(ph.metadata->>'media_type','image') = 'image'",
        "ph.moderation_status = 'approved'",
    ]
    params: list = []
    if year is not None:
        params.append(year)
        i = len(params)
        # A photo belongs to year X if it's tagged X at upload time, OR it
        # contains a face of someone canonically of that year — a student with
        # graduation_year = X, or a collaborator whose entry..exit range covers
        # X. This lets untagged uploads still surface in the right turma once
        # the people in them are identified via /contribute.
        where.append(
            f"""(
              (ph.metadata->>'graduation_year' ~ '^\\d+$'
               and (ph.metadata->>'graduation_year')::int = ${i})
              or exists (
                select 1
                from public.faces f
                join public.people p on p.id = f.person_id
                where f.photo_id = ph.id
                  and p.status = 'active'
                  and (
                    (p.person_type = 'student' and p.graduation_year = ${i})
                    or (
                      p.person_type = 'collaborator'
                      and (p.entry_year is not null or p.exit_year is not null)
                      and ${i} >= coalesce(p.entry_year, ${i})
                      and ${i} <= coalesce(p.exit_year, ${i})
                    )
                  )
              )
            )"""
        )
    params.append(limit)
    rows = await db.fetch(
        f"""
        select ph.id, ph.storage_bucket, ph.storage_path, ph.metadata
        from public.photos ph
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
