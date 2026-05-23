"""MongoDB connection, indexes, and FastAPI dependency."""

from __future__ import annotations

from typing import Generator

from pymongo import MongoClient
from pymongo.database import Database

from config import settings

_client: MongoClient | None = None
_db: Database | None = None


def _create_client() -> MongoClient:
    uri = settings.mongodb_uri
    if uri.startswith("mongomock://"):
        import mongomock

        return mongomock.MongoClient()
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = _create_client()
    return _client


def get_database() -> Database:
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db_name]
    return _db


def get_db() -> Generator[Database, None, None]:
    yield get_database()


def reset_client() -> None:
    """Close and drop cached client (tests)."""
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def ensure_database() -> None:
    """Create indexes required by the application."""
    db = get_database()
    db.users.create_index("email", unique=True)
    db.jobs.create_index("owner_id")
    db.jobs.create_index([("owner_id", 1), ("created_at", -1)])
    db.questions.create_index("job_id")


def ping_db() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False
