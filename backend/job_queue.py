"""Job queue abstraction.

Production:  Redis-backed RQ queue. A separate ``worker.py`` process consumes.
Dev/local:   FastAPI ``BackgroundTasks`` (in-process; OK for low volume).

The public API is intentionally tiny so callers don't need to know which
backend is active.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import BackgroundTasks

from config import settings

logger = logging.getLogger(__name__)


_redis = None
_queue = None


def _get_queue():
    """Lazy-init the RQ queue. Returns ``None`` if Redis is unavailable."""
    global _redis, _queue
    if _queue is not None:
        return _queue
    if not settings.use_redis:
        return None
    try:
        from redis import Redis
        from rq import Queue

        _redis = Redis.from_url(settings.redis_url)  # type: ignore[arg-type]
        # ``ping`` raises if the server isn't reachable; fall back to in-process.
        _redis.ping()
        _queue = Queue(settings.queue_name, connection=_redis)
        logger.info("Job queue: Redis at %s (queue=%s)", settings.redis_url, settings.queue_name)
        return _queue
    except Exception:
        logger.exception("Redis unavailable; falling back to BackgroundTasks")
        _redis = None
        _queue = None
        return None


def enqueue_extraction(
    job_id: str, background_tasks: Optional[BackgroundTasks] = None
) -> str:
    """Enqueue extraction. Returns the backend name used (``'redis'`` | ``'inproc'``)."""
    q = _get_queue()
    if q is not None:
        q.enqueue(
            "tasks.run_extraction",
            job_id,
            job_id=f"extract:{job_id}",
            result_ttl=3600,
            failure_ttl=86400,
        )
        return "redis"

    # Daemon thread keeps login/API responsive; BackgroundTasks block uvicorn reload.
    import threading

    from tasks import run_extraction

    threading.Thread(
        target=run_extraction, args=(job_id,), daemon=True, name=f"extract-{job_id}"
    ).start()
    return "thread"


def ping_queue() -> bool:
    """Used by the readiness endpoint."""
    if not settings.use_redis:
        return True  # in-proc backend is always 'ready'
    try:
        from redis import Redis

        r = Redis.from_url(settings.redis_url)  # type: ignore[arg-type]
        return bool(r.ping())
    except Exception:
        return False
