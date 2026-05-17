"""HTTP client for the ML service."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


class MLClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings().ml_internal_url,
            timeout=httpx.Timeout(60.0, connect=5.0),
        )

    async def analyze(self, image_bytes: bytes, filename: str = "upload.jpg") -> list[dict[str, Any]]:
        files = {"file": (filename, image_bytes, "image/jpeg")}
        response = await self._client.post("/analyze", files=files)
        response.raise_for_status()
        return response.json()["faces"]

    async def health(self) -> dict[str, Any]:
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()


_client: MLClient | None = None


def ml_client() -> MLClient:
    global _client
    if _client is None:
        _client = MLClient()
    return _client
