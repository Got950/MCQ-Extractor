"""Extraction progress stored in MongoDB (works across Render instances)."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_progress: dict[str, dict[str, int | str]] = {}


def set_progress(job_id: str, *, current: int, total: int, label: str = "") -> None:
    payload = {"current": current, "total": total, "label": label or ""}
    with _lock:
        _progress[job_id] = payload
    try:
        from database import get_database

        get_database().jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "progress_current": current,
                    "progress_total": total,
                    "progress_label": label or "",
                }
            },
        )
    except Exception:
        logger.exception("Failed to persist progress for job %s", job_id)


def get_progress(job_id: str) -> dict[str, int | str] | None:
    try:
        from database import get_database
        from repos import find_job_by_id

        job = find_job_by_id(get_database(), job_id)
        if job and job.progress_total and job.progress_total > 0:
            return {
                "current": job.progress_current or 0,
                "total": job.progress_total,
                "label": job.progress_label or "",
            }
    except Exception:
        logger.exception("Failed to read progress for job %s", job_id)

    with _lock:
        if job_id in _progress:
            return dict(_progress[job_id])
    return None


def clear_progress(job_id: str) -> None:
    with _lock:
        _progress.pop(job_id, None)
    try:
        from database import get_database

        get_database().jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "progress_current": 0,
                    "progress_total": 0,
                    "progress_label": "",
                }
            },
        )
    except Exception:
        logger.exception("Failed to clear progress for job %s", job_id)
