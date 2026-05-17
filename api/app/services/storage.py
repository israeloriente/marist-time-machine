"""Supabase Storage client (service-role)."""

from __future__ import annotations

from supabase import Client, create_client

from ..config import settings

_client: Client | None = None


def storage_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings().supabase_url, settings().supabase_service_key)
    return _client


def download(bucket: str, path: str) -> bytes:
    return storage_client().storage.from_(bucket).download(path)


def signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    result = storage_client().storage.from_(bucket).create_signed_url(path, expires_in)
    return result["signedURL"]


def public_url(bucket: str, path: str) -> str:
    return storage_client().storage.from_(bucket).get_public_url(path)
