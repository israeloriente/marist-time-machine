"""Reports: users flag photos/faces they want removed.

A report is created by any authenticated user pointing at a photo (or a
specific face within a photo). It enters a `pending` queue that admins
work through. Resolving = either removing the media (`resolved_removed`)
or rejecting the request (`resolved_rejected`). We keep resolved rows
for audit.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db
from ..deps import CurrentUser, RequireAdmin, User
from ..services import storage

router = APIRouter(prefix="/reports", tags=["reports"])


# ----------------------------- Models ---------------------------------------

class ReportIn(BaseModel):
    photo_id: UUID | None = None
    face_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=2000)
    contact_info: str | None = Field(default=None, max_length=300)


class ReportOut(BaseModel):
    id: UUID
    reporter_id: UUID | None
    reporter_email: str | None
    photo_id: UUID | None
    face_id: UUID | None
    reason: str
    contact_info: str | None
    status: str
    resolution_note: str | None
    resolved_at: str | None
    resolved_by: UUID | None
    created_at: str
    # Hydration for admin UI
    photo_signed_url: str | None = None
    photo_thumb_signed_url: str | None = None
    uploader_email: str | None = None


class ResolveIn(BaseModel):
    action: str  # 'remove' or 'reject'
    note: str | None = Field(default=None, max_length=2000)


# ----------------------------- Helpers --------------------------------------

def _hydrate(row) -> ReportOut:
    out = ReportOut(
        id=row["id"],
        reporter_id=row["reporter_id"],
        reporter_email=row["reporter_email"],
        photo_id=row["photo_id"],
        face_id=row["face_id"],
        reason=row["reason"],
        contact_info=row["contact_info"],
        status=row["status"],
        resolution_note=row["resolution_note"],
        resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
        resolved_by=row["resolved_by"],
        created_at=row["created_at"].isoformat(),
        uploader_email=row.get("uploader_email") if hasattr(row, "get") else (
            row["uploader_email"] if "uploader_email" in row.keys() else None
        ),
    )
    bucket = row["photo_bucket"] if "photo_bucket" in row.keys() else None
    path = row["photo_path"] if "photo_path" in row.keys() else None
    meta = row["photo_metadata"] if "photo_metadata" in row.keys() else None
    if bucket and path:
        out.photo_signed_url = storage.signed_url(bucket, path)
        coerced = storage.coerce_metadata(meta)
        out.photo_thumb_signed_url = storage.thumb_signed_url(coerced, bucket, path)
    return out


# ----------------------------- Endpoints ------------------------------------

@router.post("", response_model=ReportOut, status_code=201)
async def create_report(body: ReportIn, user: User = CurrentUser) -> ReportOut:
    """Flag a photo or face for removal. Any authenticated user can call."""
    if body.photo_id is None and body.face_id is None:
        raise HTTPException(
            status_code=400, detail="informe photo_id ou face_id"
        )

    # If face_id is given but photo_id isn't, derive photo_id from the face row.
    photo_id = body.photo_id
    if body.face_id is not None and photo_id is None:
        face_row = await db.fetchrow(
            "select photo_id from public.faces where id = $1", body.face_id
        )
        if face_row:
            photo_id = face_row["photo_id"]

    row = await db.fetchrow(
        """
        insert into public.reports
          (reporter_id, reporter_email, photo_id, face_id, reason, contact_info)
        values ($1, $2, $3, $4, $5, $6)
        returning id, reporter_id, reporter_email, photo_id, face_id, reason,
                  contact_info, status, resolution_note, resolved_at, resolved_by,
                  created_at
        """,
        UUID(user.id),
        user.email,
        photo_id,
        body.face_id,
        body.reason.strip(),
        (body.contact_info or "").strip() or None,
    )
    assert row is not None
    return _hydrate(row)


@router.get("/mine", response_model=list[ReportOut])
async def my_reports(user: User = CurrentUser) -> list[ReportOut]:
    """The current user's own reports (so they can see status)."""
    rows = await db.fetch(
        """
        select r.id, r.reporter_id, r.reporter_email, r.photo_id, r.face_id,
               r.reason, r.contact_info, r.status, r.resolution_note,
               r.resolved_at, r.resolved_by, r.created_at,
               p.storage_bucket as photo_bucket, p.storage_path as photo_path,
               p.metadata as photo_metadata,
               u.email as uploader_email
        from public.reports r
        left join public.photos p on p.id = r.photo_id
        left join auth.users u on u.id = p.uploaded_by
        where r.reporter_id = $1
        order by r.created_at desc
        """,
        UUID(user.id),
    )
    return [_hydrate(r) for r in rows]


# ------------------ Admin endpoints -----------------------------------------

@router.get("", response_model=list[ReportOut])
async def list_reports(
    status_filter: str = Query("pending", alias="status"),
    limit: int = 100,
    offset: int = 0,
    _user: User = RequireAdmin,
) -> list[ReportOut]:
    if status_filter not in {"pending", "resolved_removed", "resolved_rejected"}:
        raise HTTPException(
            status_code=400,
            detail="status must be pending|resolved_removed|resolved_rejected",
        )
    rows = await db.fetch(
        """
        select r.id, r.reporter_id, r.reporter_email, r.photo_id, r.face_id,
               r.reason, r.contact_info, r.status, r.resolution_note,
               r.resolved_at, r.resolved_by, r.created_at,
               p.storage_bucket as photo_bucket, p.storage_path as photo_path,
               p.metadata as photo_metadata,
               u.email as uploader_email
        from public.reports r
        left join public.photos p on p.id = r.photo_id
        left join auth.users u on u.id = p.uploaded_by
        where r.status = $1
        order by r.created_at desc
        limit $2 offset $3
        """,
        status_filter,
        limit,
        offset,
    )
    return [_hydrate(r) for r in rows]


@router.get("/counts")
async def counts(_user: User = RequireAdmin) -> dict:
    row = await db.fetchrow(
        """
        select
          count(*) filter (where status = 'pending')           as pending,
          count(*) filter (where status = 'resolved_removed')  as resolved_removed,
          count(*) filter (where status = 'resolved_rejected') as resolved_rejected
        from public.reports
        """
    )
    return dict(row) if row else {
        "pending": 0, "resolved_removed": 0, "resolved_rejected": 0,
    }


@router.post("/{report_id}/resolve", response_model=ReportOut)
async def resolve_report(
    report_id: UUID, body: ResolveIn, user: User = RequireAdmin
) -> ReportOut:
    """Resolve a report. `action='remove'` deletes the photo (DB + storage);
    `action='reject'` keeps the photo and marks the report as rejected."""
    if body.action not in {"remove", "reject"}:
        raise HTTPException(
            status_code=400, detail="action must be remove|reject"
        )

    report = await db.fetchrow(
        "select photo_id, face_id, status from public.reports where id = $1",
        report_id,
    )
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    if report["status"] != "pending":
        raise HTTPException(status_code=409, detail="report already resolved")

    if body.action == "remove" and report["photo_id"]:
        # Delete the photo entirely (cascades to faces and our face-cluster
        # work). Mirror the bulk-delete logic from photos.py to keep storage
        # objects in sync.
        photo = await db.fetchrow(
            """
            select storage_bucket, storage_path, metadata
            from public.photos where id = $1
            """,
            report["photo_id"],
        )
        if photo:
            meta = storage.coerce_metadata(photo["metadata"])
            try:
                storage.remove(photo["storage_bucket"], [photo["storage_path"]])
            except Exception:
                pass
            thumb_bucket = meta.get("thumb_bucket")
            thumb_path = meta.get("thumb_path")
            if thumb_bucket and thumb_path:
                try:
                    storage.remove(thumb_bucket, [thumb_path])
                except Exception:
                    pass
            await db.execute(
                "delete from public.photos where id = $1", report["photo_id"]
            )

    new_status = "resolved_removed" if body.action == "remove" else "resolved_rejected"
    row = await db.fetchrow(
        """
        update public.reports
           set status = $1,
               resolution_note = $2,
               resolved_at = now(),
               resolved_by = $3
         where id = $4
        returning id, reporter_id, reporter_email, photo_id, face_id, reason,
                  contact_info, status, resolution_note, resolved_at, resolved_by,
                  created_at
        """,
        new_status,
        (body.note or "").strip() or None,
        UUID(user.id),
        report_id,
    )
    assert row is not None
    return _hydrate(row)
