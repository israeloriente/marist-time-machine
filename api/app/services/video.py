"""Video frame extraction + multi-frame face analysis.

We sample the video at 1 fps (capped at MAX_FRAMES), run face detection on
every sampled frame, then cluster faces within the video by embedding
similarity so each real person becomes one row in public.faces — not one
row per frame they happen to appear in.

This mirrors Immich's "process video" pipeline (sample → detect → cluster
intra-video → keep best detection per cluster).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from typing import Any, Awaitable, Callable

import numpy as np

logger = logging.getLogger(__name__)

# Sampling: one frame per second, capped so we don't burn CPU on long clips.
SAMPLE_FPS = 1.0
MAX_FRAMES = 60

# Frame downscaling (matches the old single-frame extractor — InsightFace
# happily detects faces at this resolution and it keeps the network hop
# to the ML service cheap).
SCALE_W = 1280

# Two embeddings whose cosine distance is below this threshold are treated
# as the same person within the same video. Same value as the global
# clustering threshold so behavior is consistent.
INTRA_VIDEO_DIST = 0.4

# Max concurrent ML calls per video. The ML service is single-instance on
# CPU; firing 60 simultaneous requests would just queue up at the GIL and
# add latency. 4 keeps it busy without thrashing.
ML_CONCURRENCY = 4


# -----------------------------------------------------------------------------
# ffmpeg helpers
# -----------------------------------------------------------------------------

async def extract_thumbnail(video_bytes: bytes, seek_seconds: float = 1.0) -> bytes:
    """Single representative frame at ~1s in.

    Kept for backwards-compat (the legacy /photos/regenerate-thumbnails
    endpoint and the fallback path still call this).
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
            "-vf", f"scale='min({SCALE_W},iw)':-1",
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


async def _probe_duration(src_path: str) -> float | None:
    """Best-effort duration probe via ffprobe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            src_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        return float(out.decode().strip())
    except (ValueError, OSError):
        return None


async def sample_frames(
    video_bytes: bytes,
    fps: float = SAMPLE_FPS,
    max_frames: int = MAX_FRAMES,
) -> list[tuple[float, bytes]]:
    """Sample frames from the video at the requested fps.

    Returns a list of (timestamp_seconds, jpeg_bytes). If the video is
    long enough that fps*duration exceeds max_frames, we drop fps so the
    samples remain evenly spaced across the whole clip.
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as src:
        src.write(video_bytes)
        src_path = src.name
    dst_dir = tempfile.mkdtemp(prefix="mtm_frames_")

    try:
        duration = await _probe_duration(src_path)
        effective_fps = fps
        if duration and duration * fps > max_frames:
            # Spread max_frames evenly over the whole duration. Add 1 so the
            # last frame doesn't fall off the end.
            effective_fps = max_frames / max(duration, 1.0)

        # ffmpeg emits frame_0001.jpg, frame_0002.jpg, …
        # `-frame_pts 1` would let us reuse PTS but the timestamp from the
        # frame index (i / fps) is accurate enough and simpler.
        pattern = os.path.join(dst_dir, "frame_%04d.jpg")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i", src_path,
            "-vf", f"fps={effective_fps:.4f},scale='min({SCALE_W},iw)':-1",
            "-q:v", "3",
            "-frames:v", str(max_frames),
            pattern,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg sample_frames failed: {stderr.decode(errors='replace')[:500]}"
            )

        files = sorted(f for f in os.listdir(dst_dir) if re.match(r"frame_\d+\.jpg", f))
        out: list[tuple[float, bytes]] = []
        for f in files:
            idx_match = re.search(r"(\d+)", f)
            if not idx_match:
                continue
            idx = int(idx_match.group(1))
            ts = (idx - 1) / effective_fps  # ffmpeg's nth frame at (n-1)/fps
            with open(os.path.join(dst_dir, f), "rb") as fh:
                out.append((ts, fh.read()))
        return out
    finally:
        try:
            os.unlink(src_path)
        except OSError:
            pass
        shutil.rmtree(dst_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# Multi-frame analysis + intra-video clustering
# -----------------------------------------------------------------------------

def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 1.0
    return float(1.0 - np.dot(a, b) / (na * nb))


def _cluster_faces(
    detections: list[dict[str, Any]],
    threshold: float = INTRA_VIDEO_DIST,
) -> list[dict[str, Any]]:
    """Greedy single-link clustering by embedding cosine distance.

    Each input detection is {frame_idx, timestamp, frame_bytes, bbox,
    landmarks, detection_score, embedding}. Output: one representative
    detection per cluster — the one with the highest detection_score.
    """
    if not detections:
        return []

    # Pre-compute numpy arrays
    embeddings = [np.array(d["embedding"], dtype=np.float32) for d in detections]
    assigned = [-1] * len(detections)
    clusters: list[list[int]] = []

    for i, emb in enumerate(embeddings):
        # Compare against the centroid of each existing cluster
        for cidx, member_idxs in enumerate(clusters):
            centroid = np.mean([embeddings[j] for j in member_idxs], axis=0)
            if _cosine_distance(emb, centroid) <= threshold:
                clusters[cidx].append(i)
                assigned[i] = cidx
                break
        if assigned[i] == -1:
            clusters.append([i])
            assigned[i] = len(clusters) - 1

    # Pick the representative per cluster: highest detection_score wins.
    reps: list[dict[str, Any]] = []
    for member_idxs in clusters:
        best = max(member_idxs, key=lambda j: detections[j]["detection_score"])
        rep = dict(detections[best])
        rep["track_size"] = len(member_idxs)
        rep["first_seen_ts"] = min(detections[j]["timestamp"] for j in member_idxs)
        rep["last_seen_ts"] = max(detections[j]["timestamp"] for j in member_idxs)
        reps.append(rep)

    return reps


async def analyze_video(
    video_bytes: bytes,
    analyze_frame: Callable[[bytes, str], Awaitable[list[dict[str, Any]]]],
    fps: float = SAMPLE_FPS,
    max_frames: int = MAX_FRAMES,
) -> tuple[list[dict[str, Any]], bytes]:
    """Full pipeline: sample → detect each frame → cluster within video.

    Args:
        video_bytes: raw video bytes
        analyze_frame: async callable (frame_jpeg, filename) -> [face dicts]
                       (we inject ml_client().analyze so this module stays
                       free of the HTTP-client dependency)
        fps, max_frames: see sample_frames

    Returns:
        (representative_faces, thumbnail_jpeg)

        representative_faces is one dict per real person detected in the
        video, ready to insert into public.faces. Each carries the same
        keys analyze() returned plus track_size / first_seen_ts /
        last_seen_ts (informational).

        thumbnail_jpeg is the frame containing the highest-confidence
        face we found — or the standard "1 second in" thumbnail if no
        faces were detected at all.
    """
    frames = await sample_frames(video_bytes, fps=fps, max_frames=max_frames)
    if not frames:
        # Couldn't sample anything — fall back to the legacy single-frame
        # path so callers always get *some* thumbnail.
        thumb = await extract_thumbnail(video_bytes)
        return [], thumb

    # Detect faces in every sampled frame, with bounded concurrency.
    # The ML service is the bottleneck so we don't want to flood it.
    sem = asyncio.Semaphore(ML_CONCURRENCY)

    async def _run(ts: float, idx: int, jpeg: bytes):
        async with sem:
            try:
                faces = await analyze_frame(jpeg, f"frame_{idx:04d}.jpg")
            except Exception as exc:
                logger.warning("frame %d analyze failed: %s", idx, exc)
                return ts, idx, jpeg, []
            return ts, idx, jpeg, faces

    results = await asyncio.gather(*[
        _run(ts, idx, jpeg) for idx, (ts, jpeg) in enumerate(frames)
    ])

    all_detections: list[dict[str, Any]] = []
    best_face_score = -1.0
    best_face_frame: bytes | None = None
    for ts, idx, jpeg, faces in results:
        for f in faces:
            if f["detection_score"] > best_face_score:
                best_face_score = f["detection_score"]
                best_face_frame = jpeg
            all_detections.append({
                **f,
                "frame_idx": idx,
                "timestamp": ts,
                # NB: we don't keep the per-detection jpeg here — only the
                # best one is needed (for the video's thumbnail).
            })

    representatives = _cluster_faces(all_detections)

    # Thumbnail: the frame with the highest-confidence face; or the
    # first sampled frame as fallback; or legacy 1-second extractor if
    # ALL sampling failed (already handled above).
    thumb = best_face_frame or frames[0][1]
    return representatives, thumb
