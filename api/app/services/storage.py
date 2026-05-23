"""Supabase Storage client (service-role)."""

from __future__ import annotations

import os
import re
import unicodedata

from supabase import Client, create_client

from ..config import settings

_client: Client | None = None

# Supabase Storage rejects object keys with characters outside a conservative
# set (it returns 400 InvalidKey). Non-ASCII (ã, º), exotic whitespace like the
# narrow no-break space U+202F, and most punctuation all trip it. We keep only
# a safe subset for the *storage key* — the human-readable name is preserved
# separately in photos.original_filename.
_KEY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_key_name(name: str) -> str:
    """Make a single path segment safe to use as a Supabase Storage key.

    Strips the directory part, transliterates accents to ASCII, collapses any
    run of unsafe characters to a single '-', and guarantees a non-empty result.
    """
    name = os.path.basename(name or "")
    # Decompose accents (ã -> a + combining tilde) then drop the combining marks.
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    root, dot, ext = name.rpartition(".")
    stem, ext = (root, ext) if dot else (name, "")
    stem = _KEY_SAFE.sub("-", stem).strip("-._") or "upload"
    ext = _KEY_SAFE.sub("", ext)
    return f"{stem}.{ext}" if ext else stem


def storage_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings().supabase_url, settings().supabase_service_key)
    return _client


def _public_base() -> str:
    """Browser-reachable base URL for Supabase. Falls back to supabase_url."""
    base = settings().supabase_public_url or settings().supabase_url
    return base.rstrip("/")


def download(bucket: str, path: str) -> bytes:
    return storage_client().storage.from_(bucket).download(path)


def remove(bucket: str, paths: list[str]) -> None:
    """Best-effort delete of one or more objects in a bucket.

    Supabase Storage forwards the DELETE to the backing S3 (Hetzner Object
    Storage in our case), so this also removes the bytes from the bucket.
    Silently swallows errors per-path (an object might already be missing).
    """
    if not paths:
        return
    try:
        storage_client().storage.from_(bucket).remove(paths)
    except Exception:
        # Don't block the caller — log via stderr happens at request handler
        pass


def signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    """Returns an absolute URL signed for browser access.

    The Supabase Python client returns the URL prefixed with the storage
    client's base (which is the internal Kong hostname inside Docker).
    We strip that and prepend the public Supabase URL so the browser can fetch.
    """
    result = storage_client().storage.from_(bucket).create_signed_url(path, expires_in)
    raw = result.get("signedURL") or result.get("signedUrl") or ""
    if not raw:
        raise RuntimeError(f"empty signed URL response: {result}")

    # The client may return either a relative path (/object/sign/...) or a
    # full URL with the internal hostname (http://kong:8000/...). Normalize.
    if raw.startswith("http://") or raw.startswith("https://"):
        # Strip everything up to /storage/v1 or /object
        for marker in ("/storage/v1/", "/object/"):
            idx = raw.find(marker)
            if idx != -1:
                raw = raw[idx:]
                break

    # Ensure the path is rooted at /storage/v1
    if raw.startswith("/object/") or raw.startswith("/render/"):
        raw = "/storage/v1" + raw
    elif not raw.startswith("/storage/v1/"):
        raw = "/storage/v1/" + raw.lstrip("/")

    return _public_base() + raw


def public_url(bucket: str, path: str) -> str:
    return f"{_public_base()}/storage/v1/object/public/{bucket}/{path}"


def coerce_metadata(raw) -> dict:
    """Tolerate legacy double-encoded jsonb rows where metadata is a JSON str."""
    import json
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def thumb_signed_url(metadata, default_bucket: str, default_path: str) -> str:
    """Return a signed URL for the photo's thumbnail.

    For videos we expect metadata to contain {thumb_bucket, thumb_path}.
    For photos (and videos that haven't been thumbnailed yet) we fall back
    to the original file.

    metadata may legitimately come in as None, dict, or — for legacy rows
    that were never normalized — a string. Coerced internally.
    """
    md = coerce_metadata(metadata)
    if md.get("thumb_bucket") and md.get("thumb_path"):
        try:
            return signed_url(md["thumb_bucket"], md["thumb_path"])
        except Exception:
            pass
    return signed_url(default_bucket, default_path)
