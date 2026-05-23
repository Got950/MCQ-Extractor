"""Domain models (plain dataclasses; persisted in MongoDB)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    is_active: bool
    is_superadmin: bool
    created_at: datetime


@dataclass
class Job:
    id: str
    owner_id: str
    subject: str
    language: str
    provider: str
    status: str
    pdf_key: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


@dataclass
class Question:
    id: str
    job_id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str | None
    solution: str
