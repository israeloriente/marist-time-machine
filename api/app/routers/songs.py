"""Songs: YouTube videos each user marks as meaningful at Marista.

The UI groups by uploader's graduation_year+class_letter (from user_profiles)
into a "trilha sonora da turma" mural; user can also see/edit their own list.

Songs must be approved by an admin before they show up in the public mural
or the kiosk soundtrack (mirrors the photo moderation flow).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db
from ..deps import CurrentUser, User
from ..services import youtube

router = APIRouter(prefix="/songs", tags=["songs"])


class SongIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    caption: str | None = Field(default=None, max_length=500)


class SongOut(BaseModel):
    id: UUID
    user_id: UUID
    youtube_id: str
    title: str | None
    channel: str | None
    caption: str | None
    thumbnail_url: str | None
    watch_url: str
    created_at: str
    moderation_status: str = "approved"
    moderation_note: str | None = None
    moderated_at: str | None = None
    # User profile info (denormalized for the mural)
    user_email: str | None = None
    user_graduation_year: int | None = None
    user_class_letter: str | None = None


def _safe(r, key):
    try:
        return r[key]
    except (KeyError, IndexError):
        return None


def _to_song_out(r) -> SongOut:
    return SongOut(
        id=r["id"],
        user_id=r["user_id"],
        youtube_id=r["youtube_id"],
        title=r["title"],
        channel=r["channel"],
        caption=r["caption"],
        thumbnail_url=r["thumbnail_url"],
        watch_url=youtube.watch_url(r["youtube_id"]),
        created_at=r["created_at"].isoformat(),
        moderation_status=_safe(r, "moderation_status") or "approved",
        moderation_note=_safe(r, "moderation_note"),
        moderated_at=(
            r["moderated_at"].isoformat()
            if _safe(r, "moderated_at") else None
        ),
        user_email=_safe(r, "user_email"),
        user_graduation_year=_safe(r, "user_graduation_year"),
        user_class_letter=_safe(r, "user_class_letter"),
    )


_SELECT_BASE = """
    select s.id, s.user_id, s.youtube_id, s.title, s.channel, s.caption,
           s.thumbnail_url, s.created_at,
           s.moderation_status, s.moderation_note, s.moderated_at,
           u.email as user_email,
           up.graduation_year as user_graduation_year,
           up.class_letter   as user_class_letter
    from public.songs s
    left join public.user_profiles up on up.user_id = s.user_id
    left join auth.users u            on u.id      = s.user_id
"""


@router.get("", response_model=list[SongOut])
async def list_songs(
    year: int | None = None,
    klass: str | None = Query(None, alias="class"),
    user_id: UUID | None = None,
    limit: int = 200,
    user: User = CurrentUser,
) -> list[SongOut]:
    """List songs (mural) with uploader profile info.

    Approved songs are visible to everyone. Each user additionally sees
    their own pending/rejected songs so they can track moderation status.
    Optional filters: ?year, ?class, ?user_id.
    """
    where: list[str] = []
    params: list = []

    if year is not None:
        params.append(year)
        where.append(f"up.graduation_year = ${len(params)}")
    if klass:
        params.append(klass.upper())
        where.append(f"up.class_letter = ${len(params)}")
    if user_id is not None:
        params.append(user_id)
        where.append(f"s.user_id = ${len(params)}")

    params.append(UUID(user.id))
    visibility = (
        f"(s.moderation_status = 'approved' or s.user_id = ${len(params)})"
    )
    where.append(visibility)

    where_sql = "where " + " and ".join(where)

    params.append(limit)
    sql = f"""
        {_SELECT_BASE}
        {where_sql}
        order by s.created_at desc
        limit ${len(params)}
    """
    rows = await db.fetch(sql, *params)
    return [_to_song_out(r) for r in rows]


@router.get("/random", response_model=list[SongOut])
async def random_songs(
    year: int | None = None,
    klass: str | None = Query(None, alias="class"),
    limit: int = 20,
    fallback_any: bool = True,
) -> list[SongOut]:
    """Random APPROVED songs scoped to a class+year (best-effort).

    For the kiosk soundtrack: try songs from the requested year first; if
    nothing, fall back to any approved song so we never get total silence.
    Anonymous endpoint — never returns pending/rejected.
    """
    where: list[str] = ["s.moderation_status = 'approved'"]
    params: list = []
    if year is not None:
        params.append(year)
        where.append(f"up.graduation_year = ${len(params)}")
    if klass:
        params.append(klass.upper())
        where.append(f"up.class_letter = ${len(params)}")

    params.append(limit)
    where_sql = "where " + " and ".join(where)
    rows = await db.fetch(
        f"{_SELECT_BASE} {where_sql} order by random() limit ${len(params)}",
        *params,
    )

    if not rows and fallback_any:
        rows = await db.fetch(
            f"{_SELECT_BASE} where s.moderation_status = 'approved' "
            f"order by random() limit $1",
            limit,
        )

    return [_to_song_out(r) for r in rows]


@router.get("/mine", response_model=list[SongOut])
async def my_songs(user: User = CurrentUser) -> list[SongOut]:
    rows = await db.fetch(
        f"""
        {_SELECT_BASE}
        where s.user_id = $1
        order by s.created_at desc
        """,
        UUID(user.id),
    )
    return [_to_song_out(r) for r in rows]


@router.post("", response_model=SongOut, status_code=201)
async def create_song(body: SongIn, user: User = CurrentUser) -> SongOut:
    vid = youtube.extract_video_id(body.url)
    if not vid:
        raise HTTPException(status_code=400, detail="URL do YouTube inválida")

    meta = await youtube.fetch_oembed(vid)
    caption = (body.caption or "").strip() or None

    try:
        row = await db.fetchrow(
            """
            insert into public.songs
              (user_id, youtube_id, title, channel, caption, thumbnail_url,
               moderation_status)
            values ($1, $2, $3, $4, $5, $6, 'pending')
            returning id, user_id, youtube_id, title, channel, caption,
                      thumbnail_url, created_at, moderation_status,
                      moderation_note, moderated_at
            """,
            UUID(user.id),
            vid,
            meta["title"],
            meta["channel"],
            caption,
            meta["thumbnail_url"],
        )
    except Exception as exc:
        if "songs_user_video_idx" in str(exc):
            raise HTTPException(
                status_code=409, detail="Você já adicionou essa música."
            ) from exc
        raise

    prof = await db.fetchrow(
        """
        select u.email, up.graduation_year, up.class_letter
        from auth.users u
        left join public.user_profiles up on up.user_id = u.id
        where u.id = $1
        """,
        UUID(user.id),
    )

    assert row is not None
    return SongOut(
        id=row["id"],
        user_id=row["user_id"],
        youtube_id=row["youtube_id"],
        title=row["title"],
        channel=row["channel"],
        caption=row["caption"],
        thumbnail_url=row["thumbnail_url"],
        watch_url=youtube.watch_url(row["youtube_id"]),
        created_at=row["created_at"].isoformat(),
        moderation_status=row["moderation_status"],
        moderation_note=row["moderation_note"],
        moderated_at=row["moderated_at"].isoformat() if row["moderated_at"] else None,
        user_email=(prof or {}).get("email"),
        user_graduation_year=(prof or {}).get("graduation_year"),
        user_class_letter=(prof or {}).get("class_letter"),
    )


class SongPatch(BaseModel):
    caption: str | None = Field(default=None, max_length=500)


@router.patch("/{song_id}", response_model=SongOut)
async def update_song(song_id: UUID, body: SongPatch, user: User = CurrentUser) -> SongOut:
    result = await db.execute(
        """
        update public.songs
           set caption = $1
         where id = $2 and user_id = $3
        """,
        (body.caption or "").strip() or None,
        song_id,
        UUID(user.id),
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="music not found or not yours")

    row = await db.fetchrow(
        f"{_SELECT_BASE} where s.id = $1",
        song_id,
    )
    assert row is not None
    return _to_song_out(row)


# =====================================================================
# Admin moderation
# =====================================================================

class SongModerationOut(SongOut):
    """Same shape as SongOut — kept as alias for the admin queue endpoint."""


@router.get("/moderation", response_model=list[SongModerationOut])
async def list_for_moderation(
    status_filter: str = "pending",
    limit: int = 100,
    offset: int = 0,
    _user: User = CurrentUser,
) -> list[SongModerationOut]:
    """Admin queue: list songs by moderation status."""
    if status_filter not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be pending|approved|rejected")
    rows = await db.fetch(
        f"""
        {_SELECT_BASE}
        where s.moderation_status = $1
        order by s.created_at desc
        limit $2 offset $3
        """,
        status_filter,
        limit,
        offset,
    )
    return [SongModerationOut(**_to_song_out(r).model_dump()) for r in rows]


@router.get("/moderation/counts")
async def moderation_counts(_user: User = CurrentUser) -> dict:
    row = await db.fetchrow(
        """
        select
          count(*) filter (where moderation_status = 'pending')  as pending,
          count(*) filter (where moderation_status = 'approved') as approved,
          count(*) filter (where moderation_status = 'rejected') as rejected
        from public.songs
        """
    )
    return dict(row) if row else {"pending": 0, "approved": 0, "rejected": 0}


class ModerationDecision(BaseModel):
    note: str | None = None


@router.post("/{song_id}/approve", response_model=SongModerationOut)
async def approve_song(
    song_id: UUID, body: ModerationDecision | None = None, user: User = CurrentUser
) -> SongModerationOut:
    return await _set_moderation(song_id, "approved", body, user)


@router.post("/{song_id}/reject", response_model=SongModerationOut)
async def reject_song(
    song_id: UUID, body: ModerationDecision | None = None, user: User = CurrentUser
) -> SongModerationOut:
    return await _set_moderation(song_id, "rejected", body, user)


async def _set_moderation(
    song_id: UUID, status_str: str, body: ModerationDecision | None, user: User,
) -> SongModerationOut:
    note = (body.note.strip() if body and body.note else None) or None
    result = await db.execute(
        """
        update public.songs
           set moderation_status = $1,
               moderation_note = $2,
               moderated_at = now(),
               moderated_by = $3
         where id = $4
        """,
        status_str,
        note,
        UUID(user.id),
        song_id,
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="song not found")

    row = await db.fetchrow(f"{_SELECT_BASE} where s.id = $1", song_id)
    assert row is not None
    return SongModerationOut(**_to_song_out(row).model_dump())


class BulkRequest(BaseModel):
    song_ids: list[UUID]
    note: str | None = None


class BulkResult(BaseModel):
    succeeded: list[UUID]
    failed: list[dict]


@router.post("/moderation/bulk-approve", response_model=BulkResult)
async def bulk_approve(body: BulkRequest, user: User = CurrentUser) -> BulkResult:
    return await _bulk_moderate(body, "approved", user)


@router.post("/moderation/bulk-reject", response_model=BulkResult)
async def bulk_reject(body: BulkRequest, user: User = CurrentUser) -> BulkResult:
    return await _bulk_moderate(body, "rejected", user)


async def _bulk_moderate(body: BulkRequest, status_str: str, user: User) -> BulkResult:
    if not body.song_ids:
        return BulkResult(succeeded=[], failed=[])
    note = (body.note.strip() if body.note else None) or None
    await db.execute(
        """
        update public.songs
           set moderation_status = $1,
               moderation_note   = $2,
               moderated_at      = now(),
               moderated_by      = $3
         where id = any($4::uuid[])
        """,
        status_str,
        note,
        UUID(user.id),
        body.song_ids,
    )
    return BulkResult(succeeded=body.song_ids, failed=[])


# =====================================================================
# Delete
# Admins can delete any song; regular users can only delete their own.
# =====================================================================

@router.delete("/{song_id}", status_code=204)
async def delete_song(song_id: UUID, user: User = CurrentUser):
    """Owner removes their own song from the DB.

    Admins use POST /moderation/bulk-delete to remove songs from other users.
    """
    result = await db.execute(
        "delete from public.songs where id = $1 and user_id = $2",
        song_id,
        UUID(user.id),
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="music not found or not yours")
    return None


@router.post("/moderation/bulk-delete", response_model=BulkResult)
async def bulk_delete(body: BulkRequest, _user: User = CurrentUser) -> BulkResult:
    if not body.song_ids:
        return BulkResult(succeeded=[], failed=[])
    await db.execute(
        "delete from public.songs where id = any($1::uuid[])",
        body.song_ids,
    )
    return BulkResult(succeeded=body.song_ids, failed=[])
