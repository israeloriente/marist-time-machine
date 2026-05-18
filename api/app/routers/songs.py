"""Songs: YouTube videos each user marks as meaningful at Marista.

The UI groups by uploader's graduation_year+class_letter (from user_profiles)
into a "trilha sonora da turma" mural; user can also see/edit their own list.
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
        user_email=_safe(r, "user_email"),
        user_graduation_year=_safe(r, "user_graduation_year"),
        user_class_letter=_safe(r, "user_class_letter"),
    )


@router.get("", response_model=list[SongOut])
async def list_songs(
    year: int | None = None,
    klass: str | None = Query(None, alias="class"),
    user_id: UUID | None = None,
    limit: int = 200,
    _user: User = CurrentUser,
) -> list[SongOut]:
    """List all songs (mural) with uploader profile info.

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

    where_sql = ("where " + " and ".join(where)) if where else ""

    params.append(limit)
    sql = f"""
        select s.id, s.user_id, s.youtube_id, s.title, s.channel, s.caption,
               s.thumbnail_url, s.created_at,
               u.email as user_email,
               up.graduation_year as user_graduation_year,
               up.class_letter   as user_class_letter
        from public.songs s
        left join public.user_profiles up on up.user_id = s.user_id
        left join auth.users u            on u.id      = s.user_id
        {where_sql}
        order by s.created_at desc
        limit ${len(params)}
    """
    rows = await db.fetch(sql, *params)
    return [_to_song_out(r) for r in rows]


@router.get("/mine", response_model=list[SongOut])
async def my_songs(user: User = CurrentUser) -> list[SongOut]:
    rows = await db.fetch(
        """
        select s.id, s.user_id, s.youtube_id, s.title, s.channel, s.caption,
               s.thumbnail_url, s.created_at,
               u.email as user_email,
               up.graduation_year as user_graduation_year,
               up.class_letter   as user_class_letter
        from public.songs s
        left join public.user_profiles up on up.user_id = s.user_id
        left join auth.users u            on u.id      = s.user_id
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

    # Enrich (best-effort)
    meta = await youtube.fetch_oembed(vid)
    caption = (body.caption or "").strip() or None

    try:
        row = await db.fetchrow(
            """
            insert into public.songs
              (user_id, youtube_id, title, channel, caption, thumbnail_url)
            values ($1, $2, $3, $4, $5, $6)
            returning id, user_id, youtube_id, title, channel, caption,
                      thumbnail_url, created_at
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

    # Compose return with profile info
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
        """
        select s.id, s.user_id, s.youtube_id, s.title, s.channel, s.caption,
               s.thumbnail_url, s.created_at,
               u.email as user_email,
               up.graduation_year as user_graduation_year,
               up.class_letter   as user_class_letter
        from public.songs s
        left join public.user_profiles up on up.user_id = s.user_id
        left join auth.users u            on u.id      = s.user_id
        where s.id = $1
        """,
        song_id,
    )
    assert row is not None
    return _to_song_out(row)


@router.delete("/{song_id}", status_code=204)
async def delete_song(song_id: UUID, user: User = CurrentUser):
    result = await db.execute(
        "delete from public.songs where id = $1 and user_id = $2",
        song_id,
        UUID(user.id),
    )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="music not found or not yours")
    return None
