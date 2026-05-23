"""Pytest fixtures: isolated in-memory MongoDB per test, stubbed LLM."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("MONGODB_URI", "mongomock://")
    monkeypatch.setenv("MONGODB_DB_NAME", f"test_{uuid.uuid4().hex}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("APP_SECRET", "test-secret-please-rotate")
    monkeypatch.setenv("ALLOWED_ORIGIN", "http://localhost")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("SUPERADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SUPERADMIN_PASSWORD", raising=False)

    for mod in [
        "main",
        "auth",
        "database",
        "repos",
        "models",
        "schemas",
        "security",
        "tasks",
        "storage",
        "job_queue",
        "llm_service",
        "config",
    ]:
        sys.modules.pop(mod, None)

    import database

    database.reset_client()

    yield

    database.reset_client()


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import llm_service

    def _fake_extract(pdf_path: str, subject: str, provider: str, job_id=None):
        return [
            {
                "question_text": "What is 2 + 2?",
                "options": {"A": "3", "B": "4", "C": "5", "D": "22"},
                "correct_answer": "B",
                "solution": "Add them.",
            }
        ]

    monkeypatch.setattr(llm_service, "extract_mcqs", _fake_extract)

    import job_queue

    def _sync_enqueue(job_id: str, background_tasks=None):
        from tasks import run_extraction

        run_extraction(job_id)
        return "sync"

    monkeypatch.setattr(job_queue, "enqueue_extraction", _sync_enqueue)

    import main

    return TestClient(main.app)


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"xref\n0 3\n0000000000 65535 f \n"
        b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n"
    )


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
