"""Server-side media compression before storage.

- Images: Pillow re-encode as JPEG quality 85, cap longest side at 2560px,
  honor EXIF orientation.
- Videos: ffmpeg H.264 CRF 26, cap height at 1080p, AAC 128k audio.

Both helpers fall back to the original bytes if anything goes wrong — we
never want a compression failure to block an upload.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_IMAGE_DIM = 2560
JPEG_QUALITY = 85
VIDEO_CRF = 26
VIDEO_MAX_HEIGHT = 1080


def compress_image(payload: bytes) -> tuple[bytes, str, str]:
    """Re-encode an image as JPEG with sensible web defaults.

    Returns (compressed_bytes, content_type, suggested_extension).
    Falls back to the original on any error.
    """
    try:
        with Image.open(io.BytesIO(payload)) as img:
            img = ImageOps.exif_transpose(img)  # honor camera orientation
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(
                buf,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                progressive=True,
            )
            out = buf.getvalue()
    except Exception as exc:
        logger.warning("image compression failed (%s) — using original", exc)
        return payload, "application/octet-stream", ""

    # Only return the compressed bytes if smaller — sometimes a tiny
    # already-optimized JPEG grows after re-encoding.
    if len(out) >= len(payload):
        return payload, "image/jpeg", ".jpg"
    return out, "image/jpeg", ".jpg"


async def compress_video(payload: bytes) -> tuple[bytes, str, str]:
    """Re-encode a video as H.264 mp4 with CRF 26, capped at 1080p.

    Returns (compressed_bytes, content_type, suggested_extension).
    Falls back to the original bytes if ffmpeg fails.
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as src:
        src.write(payload)
        src_path = src.name
    dst_path = src_path + ".mp4"

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i", src_path,
            "-vf", f"scale='trunc(oh*a/2)*2':'min({VIDEO_MAX_HEIGHT},ih)'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(VIDEO_CRF),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            dst_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(
                "video compression failed (ffmpeg returned %s) — using original: %s",
                proc.returncode,
                stderr.decode(errors="replace")[:300],
            )
            return payload, "video/mp4", ""

        with open(dst_path, "rb") as fh:
            out = fh.read()
    except Exception as exc:
        logger.warning("video compression crashed (%s) — using original", exc)
        return payload, "video/mp4", ""
    finally:
        for p in (src_path, dst_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    if len(out) >= len(payload):
        # Re-encoding made it bigger (common for short low-bitrate clips):
        # keep the original to save bandwidth.
        return payload, "video/mp4", ""
    return out, "video/mp4", ".mp4"
