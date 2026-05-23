"""Background tasks: PDF extraction + scheduled cleanup."""

from __future__ import annotations

import logging
from datetime import datetime

from config import settings
from database import get_database
from llm_service import extract_mcqs
from job_progress import clear_progress
from repos import (
    delete_questions_for_job,
    find_job_by_id,
    insert_questions,
    update_job,
)
from security import clean_plain, clean_rich
from storage import get_storage

logger = logging.getLogger(__name__)


def _safe_error(exc: Exception) -> str:
    msg = str(exc) or exc.__class__.__name__
    return msg[:500]


def run_extraction(job_id: str) -> None:
    """Pull a job, fetch its PDF from storage, call the LLM, persist questions."""
    db = get_database()
    storage = get_storage()
    try:
        job = find_job_by_id(db, job_id)
        if not job:
            logger.error("run_extraction: job %s missing", job_id)
            return

        update_job(db, job_id, status="processing")

        try:
            with storage.open_local(job.pdf_key) as local_path:
                questions = extract_mcqs(
                    local_path, job.subject, job.provider, job_id=job_id
                )
        except Exception as exc:
            logger.exception("Extraction failed for job %s", job_id)
            update_job(
                db,
                job_id,
                status="failed",
                error_message=_safe_error(exc),
                completed_at=datetime.utcnow(),
            )
            clear_progress(job_id)
            return

        if not questions:
            logger.warning("Job %s: extraction returned 0 questions", job_id)
            update_job(
                db,
                job_id,
                status="failed",
                error_message=(
                    "The model returned no questions. The PDF may be image-only, "
                    "scanned at low quality, or not contain recognisable MCQs."
                ),
                completed_at=datetime.utcnow(),
            )
            clear_progress(job_id)
            return

        delete_questions_for_job(db, job_id)
        rows = [
            {
                "question_text": clean_rich(q.get("question_text", "")),
                "option_a": clean_plain(q.get("options", {}).get("A", "")),
                "option_b": clean_plain(q.get("options", {}).get("B", "")),
                "option_c": clean_plain(q.get("options", {}).get("C", "")),
                "option_d": clean_plain(q.get("options", {}).get("D", "")),
                "correct_answer": q.get("correct_answer"),
                "solution": clean_rich(q.get("solution", "")),
            }
            for q in questions
        ]
        insert_questions(db, job_id, rows)

        update_job(
            db,
            job_id,
            status="done",
            completed_at=datetime.utcnow(),
            error_message=None,
        )
        clear_progress(job_id)
        logger.info("Job %s finished with %d questions", job_id, len(questions))
    finally:
        clear_progress(job_id)


def cleanup_old_uploads(ttl_hours: int | None = None) -> int:
    ttl = ttl_hours if ttl_hours is not None else settings.upload_ttl_hours
    if ttl <= 0:
        return 0

    storage = get_storage()
    older_than = ttl * 3600
    keys = storage.list_old_keys(older_than)

    deleted = 0
    for key in keys:
        try:
            storage.delete(key)
            deleted += 1
        except Exception:
            logger.exception("Cleanup: failed to delete %s", key)

    logger.info("Cleanup: removed %d files older than %d h", deleted, ttl)
    return deleted
