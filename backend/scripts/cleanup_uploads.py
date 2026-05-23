"""CLI: run upload TTL cleanup once. Designed for cron / scheduled jobs.

Usage::

    python -m scripts.cleanup_uploads            # use UPLOAD_TTL_HOURS
    python -m scripts.cleanup_uploads --hours 48 # override
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure backend package is importable when invoked as ``python scripts/...``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Delete uploads older than TTL.")
    parser.add_argument("--hours", type=int, default=None)
    args = parser.parse_args()

    from tasks import cleanup_old_uploads

    deleted = cleanup_old_uploads(ttl_hours=args.hours)
    print(f"Deleted {deleted} uploads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
