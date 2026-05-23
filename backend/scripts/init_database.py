"""CLI: connect to MongoDB, create indexes, and seed the superadmin user.

Usage::

    cd backend
    source .venv/bin/activate
    python -m scripts.init_database

Requires ``MONGODB_URI`` (MongoDB Atlas connection string) in ``.env`` or the
environment. Set ``SUPERADMIN_EMAIL`` and ``SUPERADMIN_PASSWORD`` to create the
initial superadmin account (skipped if the email already exists).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()


def _ensure_superadmin() -> None:
    from auth import hash_password
    from config import settings
    from database import get_database
    from repos import create_user, find_user_by_email

    email = settings.superadmin_email
    password = settings.superadmin_password
    if not email or not password:
        print("  Superadmin: skipped (set SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD)")
        return

    email = email.lower().strip()
    db = get_database()
    existing = find_user_by_email(db, email)
    if existing:
        print(f"  Superadmin: already exists ({email})")
        return

    create_user(
        db,
        email=email,
        password_hash=hash_password(password),
        is_superadmin=True,
    )
    print(f"  Superadmin: created ({email})")


def main() -> int:
    from config import settings
    from database import ensure_database, ping_db

    ensure_database()
    _ensure_superadmin()

    if not ping_db():
        print("ERROR: MongoDB connectivity check failed", file=sys.stderr)
        return 1

    print("Database ready.")
    print(f"  URI:      {settings.mongodb_uri[:30]}…" if len(settings.mongodb_uri) > 30 else f"  URI:      {settings.mongodb_uri}")
    print(f"  Database: {settings.mongodb_db_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
