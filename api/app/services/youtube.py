"""YouTube URL parsing + oEmbed lookup (no API key required)."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import httpx

# Matches:
#   https://www.youtube.com/watch?v=VIDEO_ID
#   https://youtube.com/watch?v=VIDEO_ID&t=...
#   https://youtu.be/VIDEO_ID
#   https://www.youtube.com/embed/VIDEO_ID
#   https://www.youtube.com/shorts/VIDEO_ID
#   https://music.youtube.com/watch?v=VIDEO_ID
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(raw: str) -> str | None:
    """Return the 11-char YouTube video id, or None if not recognized."""
    if not raw:
        return None
    raw = raw.strip()

    if _ID_RE.match(raw):
        return raw

    try:
        u = urlparse(raw)
    except Exception:
        return None

    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/", 1)[0]
        return vid if _ID_RE.match(vid) else None

    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if u.path == "/watch":
            v = parse_qs(u.query).get("v", [""])[0]
            return v if _ID_RE.match(v) else None
        for prefix in ("/embed/", "/shorts/", "/v/"):
            if u.path.startswith(prefix):
                vid = u.path[len(prefix):].split("/", 1)[0]
                return vid if _ID_RE.match(vid) else None

    return None


def thumbnail_url(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


async def fetch_oembed(video_id: str) -> dict:
    """Public oEmbed endpoint — no API key. Best-effort enrichment."""
    url = "https://www.youtube.com/oembed"
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            r = await client.get(
                url,
                params={"url": watch_url(video_id), "format": "json"},
            )
            if r.status_code == 200:
                data = r.json()
                return {
                    "title": data.get("title"),
                    "channel": data.get("author_name"),
                    "thumbnail_url": data.get("thumbnail_url") or thumbnail_url(video_id),
                }
    except Exception:
        pass
    return {
        "title": None,
        "channel": None,
        "thumbnail_url": thumbnail_url(video_id),
    }
