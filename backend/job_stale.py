"""Detect jobs stuck after server restarts or hung workers."""

from __future__ import annotations

import logging

from job_progress import clear_progress
from job_queue import enqueue_extraction
from models import Job
from repos import ensure_utc, update_job, utc_now

logger = logging.getLogger(__name__)

# Queued jobs should start within a few minutes; re-enqueue if the worker died.
STALE_QUEUED_SECONDS = 12 * 60
# Processing longer than this is treated as failed so the user can retry.
STALE_PROCESSING_SECONDS = 25 * 60


def reconcile_stale_job(db, job: Job) -> Job:
    if job.status not in ("queued", "processing"):
        return job

    age_s = (utc_now() - ensure_utc(job.created_at)).total_seconds()

    if job.status == "processing" and age_s > STALE_PROCESSING_SECONDS:
        logger.warning("Marking stale processing job %s as failed (age=%.0fs)", job.id, age_s)
        clear_progress(job.id)
        updated = update_job(
            db,
            job.id,
            status="failed",
            error_message=(
                "Extraction did not finish in time (the server may have restarted). "
                "Click Retry extraction to run again."
            ),
            completed_at=utc_now(),
        )
        return updated or job

    if job.status == "queued" and age_s > STALE_QUEUED_SECONDS:
        logger.info("Re-enqueueing stale queued job %s (age=%.0fs)", job.id, age_s)
        enqueue_extraction(job.id, None)

    return job
