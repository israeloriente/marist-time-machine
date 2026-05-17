"""DBSCAN-streaming clustering, Immich-style.

For each new face: find neighbors within `max_distance` cosine distance.
If neighbors form a "core point" (>= min_faces), assign to an existing
person if any neighbor has one, otherwise create a new person.
"""

from __future__ import annotations

from uuid import UUID

import numpy as np

from .. import db
from ..config import settings


async def assign_face_to_person(face_id: UUID, embedding: list[float]) -> UUID | None:
    """Run the streaming DBSCAN step for one freshly-inserted face."""
    cfg = settings()
    vec = np.array(embedding, dtype=np.float32)

    neighbors = await db.fetch(
        """
        select id, person_id, embedding <=> $1 as distance
        from public.faces
        where id <> $2 and embedding <=> $1 <= $3
        order by distance asc
        limit $4
        """,
        vec,
        face_id,
        cfg.cluster_max_distance,
        cfg.cluster_min_faces * 4,  # window over which we look for a label
    )

    # Find an existing person among the closest neighbors
    for row in neighbors:
        if row["person_id"] is not None:
            await db.execute(
                "update public.faces set person_id = $1 where id = $2",
                row["person_id"],
                face_id,
            )
            return row["person_id"]

    # No labeled neighbor — is this face a core point?
    if len(neighbors) >= cfg.cluster_min_faces:
        new_person = await db.fetchrow(
            "insert into public.people (thumbnail_face_id) values ($1) returning id",
            face_id,
        )
        assert new_person is not None
        person_id = new_person["id"]

        # Label this face and its unlabeled neighbors
        neighbor_ids = [face_id, *(row["id"] for row in neighbors if row["person_id"] is None)]
        await db.execute(
            """
            update public.faces
            set person_id = $1
            where id = any($2::uuid[]) and person_id is null
            """,
            person_id,
            neighbor_ids,
        )
        return person_id

    # Not enough neighbors yet — leave unlabeled
    return None
