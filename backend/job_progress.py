"""In-memory extraction progress (dev / single-worker)."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_progress: dict[str, dict[str, int | str]] = {}


def set_progress(job_id: str, *, current: int, total: int, label: str = "") -> None:
    with _lock:
        _progress[job_id] = {"current": current, "total": total, "label": label}


def get_progress(job_id: str) -> dict[str, int | str] | None:
    with _lock:
        return dict(_progress[job_id]) if job_id in _progress else None


def clear_progress(job_id: str) -> None:
    with _lock:
        _progress.pop(job_id, None)
