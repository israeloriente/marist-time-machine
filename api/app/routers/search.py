"""Search: the core "time machine" endpoint.

User uploads a selfie -> we run detection+embedding -> find the nearest
person cluster -> return every photo where that person appears.
"""

from __future__ import annotations

import logging
from uuid import UUID

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db
from ..config import settings
from ..deps import CurrentUser, User
from ..services import storage
from ..services.ml_client import ml_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


class MatchedPhoto(BaseModel):
    photo_id: UUID
    storage_bucket: str
    storage_path: str
    uploaded_at: str
    signed_url: str
    distance: float


class SearchResponse(BaseModel):
    person_id: UUID | None
    matched_faces: int
    photos: list[MatchedPhoto]


@router.post("", response_model=SearchResponse)
async def search_by_face(
    file: UploadFile = File(...),
    limit: int = 50,
    user: User = CurrentUser,
) -> SearchResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="must be an image")
    payload = await file.read()
    faces = await ml_client().analyze(payload, file.filename or "query.jpg")
    if not faces:
        raise HTTPException(status_code=422, detail="no face detected in query image")

    # Use the highest-scoring face as the query
    faces.sort(key=lambda f: f["detection_score"], reverse=True)
    query = np.array(faces[0]["embedding"], dtype=np.float32)
    # Clustering threshold is tighter than search threshold. Use a wider
    # window for retrieval (still constrained by the cosine distance).
    search_distance = max(settings().cluster_max_distance, 0.65)

    # Debug: log the top 5 distances from the query for diagnostics.
    top = await db.fetch(
        "select id, person_id, embedding <=> $1 as distance from public.faces order by distance asc limit 5",
        query,
    )
    logger.info(
        "search: query detection_score=%.3f | search_distance=%.2f | top5_distances=%s",
        faces[0]["detection_score"],
        search_distance,
        [round(float(r["distance"]), 3) for r in top],
    )

    nearest = await db.fetchrow(
        """
        select person_id, embedding <=> $1 as distance
        from public.faces
        where person_id is not null and embedding <=> $1 <= $2
        order by distance asc
        limit 1
        """,
        query,
        search_distance,
    )

    if nearest is None:
        # Fall back to raw face-to-face matches if no clustered person within range
        raw = await db.fetch(
            """
            select f.id, f.photo_id, p.storage_bucket, p.storage_path, p.uploaded_at,
                   f.embedding <=> $1 as distance
            from public.faces f
            join public.photos p on p.id = f.photo_id
            order by distance asc
            limit $2
            """,
            query,
            limit,
        )
        photos = []
        for r in raw:
            if r["distance"] > search_distance:
                continue
            url = storage.signed_url(r["storage_bucket"], r["storage_path"])
            photos.append(
                MatchedPhoto(
                    photo_id=r["photo_id"],
                    storage_bucket=r["storage_bucket"],
                    storage_path=r["storage_path"],
                    uploaded_at=r["uploaded_at"].isoformat(),
                    signed_url=url,
                    distance=float(r["distance"]),
                )
            )
        return SearchResponse(person_id=None, matched_faces=len(photos), photos=photos)

    person_id = nearest["person_id"]

    rows = await db.fetch(
        """
        select ph.id as photo_id, ph.storage_bucket, ph.storage_path, ph.uploaded_at,
               min(f.embedding <=> $1) as distance
        from public.faces f
        join public.photos ph on ph.id = f.photo_id
        where f.person_id = $2
        group by ph.id, ph.storage_bucket, ph.storage_path, ph.uploaded_at
        order by distance asc
        limit $3
        """,
        query,
        person_id,
        limit,
    )

    photos = []
    for r in rows:
        url = storage.signed_url(r["storage_bucket"], r["storage_path"])
        photos.append(
            MatchedPhoto(
                photo_id=r["photo_id"],
                storage_bucket=r["storage_bucket"],
                storage_path=r["storage_path"],
                uploaded_at=r["uploaded_at"].isoformat(),
                signed_url=url,
                distance=float(r["distance"]),
            )
        )

    photos.sort(key=lambda p: p.distance)
    _ = user  # auth required, identity unused for now
    return SearchResponse(person_id=person_id, matched_faces=len(photos), photos=photos)
