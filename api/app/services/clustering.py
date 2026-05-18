"""DBSCAN-streaming clustering, Immich-style.

For each new face: find neighbors within `max_distance` cosine distance.
If neighbors form a "core point" (>= min_faces), assign to an existing
person if any neighbor has one, otherwise create a new person.
"""

from __future__ import annotations

import logging
from uuid import UUID

import numpy as np

from .. import db
from ..config import settings

logger = logging.getLogger(__name__)


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


async def recluster_all(reset: bool = True) -> dict:
    """Re-run DBSCAN over every face. Mirrors Immich's nightly recluster job.

    Named people (those with display_name set) are **preserved**: their
    person row and all their face assignments survive the recluster. Only
    anonymous people get wiped and their faces re-clustered from scratch.

    If `reset=False`, just clusters whatever is currently unassigned (used
    by streaming ingest).

    Returns counts of faces processed, faces newly assigned, people created.
    """
    cfg = settings()

    if reset:
        # Detach faces from anonymous people, then delete those anonymous people.
        # Named people (and their face assignments) stay intact.
        await db.execute(
            """
            update public.faces f
               set person_id = null
              from public.people p
             where f.person_id = p.id
               and p.display_name is null
            """,
        )
        await db.execute(
            "delete from public.people where display_name is null",
        )
        logger.info("recluster: cleared anonymous people + their assignments")

    # Process faces in descending detection_score order (best detections first
    # are more likely to become reliable cluster cores).
    faces = await db.fetch(
        """
        select id, embedding, detection_score
        from public.faces
        where person_id is null
        order by detection_score desc nulls last
        """,
    )
    logger.info("recluster: processing %d faces", len(faces))

    assigned = 0
    people_created = 0

    for row in faces:
        face_id = row["id"]
        # The DB returns embedding as a numpy array thanks to pgvector codec.
        emb = row["embedding"]
        if emb is None:
            continue

        neighbors = await db.fetch(
            """
            select id, person_id, embedding <=> $1 as distance
            from public.faces
            where id <> $2 and embedding <=> $1 <= $3
            order by distance asc
            limit $4
            """,
            emb,
            face_id,
            cfg.cluster_max_distance,
            cfg.cluster_min_faces * 4,
        )

        # 1) Adopt nearest labeled neighbor's person
        adopted = False
        for n in neighbors:
            if n["person_id"] is not None:
                await db.execute(
                    "update public.faces set person_id = $1 where id = $2",
                    n["person_id"],
                    face_id,
                )
                assigned += 1
                adopted = True
                break
        if adopted:
            continue

        # 2) If core point, create new person and label neighbors
        if len(neighbors) >= cfg.cluster_min_faces:
            new_person = await db.fetchrow(
                "insert into public.people (thumbnail_face_id) values ($1) returning id",
                face_id,
            )
            assert new_person is not None
            pid = new_person["id"]
            people_created += 1
            ids_to_label = [face_id, *(n["id"] for n in neighbors if n["person_id"] is None)]
            await db.execute(
                """
                update public.faces
                set person_id = $1
                where id = any($2::uuid[]) and person_id is null
                """,
                pid,
                ids_to_label,
            )
            assigned += len(ids_to_label)

    summary = {
        "faces_processed": len(faces),
        "faces_assigned": assigned,
        "people_created": people_created,
    }
    logger.info("recluster: done %s", summary)
    return summary


async def stats() -> dict:
    row = await db.fetchrow(
        """
        select
          (select count(*) from public.faces) as faces_total,
          (select count(*) from public.faces where person_id is not null) as faces_clustered,
          (select count(*) from public.people) as people
        """,
    )
    assert row is not None
    return dict(row)
