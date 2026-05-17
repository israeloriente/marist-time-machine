"""Background job scheduler.

Runs in the same process as the FastAPI app. A single async lock guards the
recluster job — if the previous tick is still running, the next is skipped.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .services.clustering import recluster_all

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_recluster_lock = asyncio.Lock()
_last_result: dict = {}


async def _run_recluster() -> None:
    if _recluster_lock.locked():
        logger.info("recluster skipped: previous run still in progress")
        return
    async with _recluster_lock:
        started = datetime.now(timezone.utc)
        logger.info("recluster: scheduled run started at %s", started.isoformat())
        try:
            result = await recluster_all(reset=True)
            _last_result.clear()
            _last_result.update({
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "result": result,
            })
            logger.info("recluster: scheduled run finished %s", result)
        except Exception as exc:
            logger.exception("recluster: scheduled run failed")
            _last_result.update({
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })


def start() -> None:
    global _scheduler
    cron = settings().recluster_cron.strip()
    if not cron:
        logger.info("recluster scheduler disabled (RECLUSTER_CRON empty)")
        return
    try:
        trigger = CronTrigger.from_crontab(cron, timezone="UTC")
    except Exception:
        logger.exception("invalid RECLUSTER_CRON=%r, scheduler disabled", cron)
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_recluster,
        trigger=trigger,
        id="recluster_nightly",
        max_instances=1,  # belt and suspenders alongside the asyncio lock
        coalesce=True,    # if missed (e.g. container down), run once when up
    )
    _scheduler.start()
    next_fire = _scheduler.get_job("recluster_nightly").next_run_time
    logger.info("recluster scheduler started: cron=%r next=%s", cron, next_fire)


def stop() -> None:
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)


def last_result() -> dict:
    return dict(_last_result)


def next_run_iso() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("recluster_nightly")
    if job is None or job.next_run_time is None:
        return None
    return job.next_run_time.isoformat()
