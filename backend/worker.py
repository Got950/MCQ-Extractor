"""Standalone RQ worker entry point.

Run with::

    cd backend
    python worker.py                  # default queue from settings
    python worker.py extra-queue ...  # override queues

Requires ``REDIS_URL`` to be set. If not set, this script exits with a clear
error so you don't accidentally start an idle worker.
"""

from __future__ import annotations

import logging
import sys

from redis import Redis
from rq import Queue, Worker

from config import settings


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log = logging.getLogger("worker")

    if not settings.redis_url:
        log.error("REDIS_URL is not configured; cannot start RQ worker.")
        return 2

    redis_conn = Redis.from_url(settings.redis_url)
    redis_conn.ping()

    queue_names = argv[1:] if len(argv) > 1 else [settings.queue_name]
    queues = [Queue(name, connection=redis_conn) for name in queue_names]
    log.info("Starting worker on queues: %s", queue_names)

    worker = Worker(queues, connection=redis_conn)
    worker.work(with_scheduler=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
