"""Video frame extraction. Mirrors Immich: one representative frame per video."""

from __future__ import annotations

import asyncio
import os
import tempfile


async def extract_thumbnail(video_bytes: bytes, seek_seconds: float = 1.0) -> bytes:
    """Run ffmpeg to extract a single JPEG frame from the video.

    Seeks ~1s in (skipping the first frame which is often black).
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as src:
        src.write(video_bytes)
        src_path = src.name
    dst_path = src_path + ".jpg"

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-ss", str(seek_seconds),
            "-i", src_path,
            "-frames:v", "1",
            "-q:v", "2",
            "-vf", "scale='min(1280,iw)':-1",
            dst_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:500]}")

        with open(dst_path, "rb") as fh:
            return fh.read()
    finally:
        for p in (src_path, dst_path):
            try:
                os.unlink(p)
            except OSError:
                pass
