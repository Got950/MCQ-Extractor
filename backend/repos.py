"""MongoDB data access for users, jobs, and questions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from models import Job, Question, User


def _user_from_doc(doc: dict[str, Any]) -> User:
    return User(
        id=str(doc["_id"]),
        email=doc["email"],
        password_hash=doc["password_hash"],
        is_active=bool(doc.get("is_active", True)),
        is_superadmin=bool(doc.get("is_superadmin", False)),
        created_at=doc["created_at"],
    )


def _job_from_doc(doc: dict[str, Any]) -> Job:
    return Job(
        id=str(doc["_id"]),
        owner_id=doc["owner_id"],
        subject=doc["subject"],
        language=doc.get("language", "English"),
        provider=doc["provider"],
        status=doc["status"],
        pdf_key=doc["pdf_key"],
        error_message=doc.get("error_message"),
        created_at=doc["created_at"],
        completed_at=doc.get("completed_at"),
        progress_current=int(doc.get("progress_current") or 0),
        progress_total=int(doc.get("progress_total") or 0),
        progress_label=str(doc.get("progress_label") or ""),
    )


def _question_from_doc(doc: dict[str, Any]) -> Question:
    return Question(
        id=str(doc["_id"]),
        job_id=doc["job_id"],
        question_text=doc.get("question_text", ""),
        option_a=doc.get("option_a", ""),
        option_b=doc.get("option_b", ""),
        option_c=doc.get("option_c", ""),
        option_d=doc.get("option_d", ""),
        correct_answer=doc.get("correct_answer"),
        solution=doc.get("solution", ""),
    )


# --- Users -------------------------------------------------------------------
def find_user_by_email(db: Database, email: str) -> User | None:
    doc = db.users.find_one({"email": email})
    return _user_from_doc(doc) if doc else None


def find_user_by_id(db: Database, user_id: str) -> User | None:
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        return None
    doc = db.users.find_one({"_id": oid})
    return _user_from_doc(doc) if doc else None


def create_user(
    db: Database,
    *,
    email: str,
    password_hash: str,
    is_superadmin: bool = False,
) -> User:
    now = datetime.utcnow()
    doc = {
        "email": email,
        "password_hash": password_hash,
        "is_active": True,
        "is_superadmin": is_superadmin,
        "created_at": now,
    }
    try:
        result = db.users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("email_exists") from exc
    doc["_id"] = result.inserted_id
    return _user_from_doc(doc)


def count_jobs_for_user(db: Database, owner_id: str) -> int:
    return db.jobs.count_documents({"owner_id": owner_id})


# --- Jobs --------------------------------------------------------------------
def create_job(
    db: Database,
    *,
    job_id: str,
    owner_id: str,
    subject: str,
    language: str,
    provider: str,
    pdf_key: str,
    status: str = "queued",
) -> Job:
    now = datetime.utcnow()
    doc = {
        "_id": job_id,
        "owner_id": owner_id,
        "subject": subject,
        "language": language,
        "provider": provider,
        "status": status,
        "pdf_key": pdf_key,
        "error_message": None,
        "created_at": now,
        "completed_at": None,
    }
    db.jobs.insert_one(doc)
    return _job_from_doc(doc)


def find_job_by_id(db: Database, job_id: str) -> Job | None:
    doc = db.jobs.find_one({"_id": job_id})
    return _job_from_doc(doc) if doc else None


def list_jobs_for_user(db: Database, owner_id: str, *, limit: int = 50) -> list[Job]:
    cursor = (
        db.jobs.find({"owner_id": owner_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [_job_from_doc(doc) for doc in cursor]


def update_job(db: Database, job_id: str, **fields: Any) -> Job | None:
    if not fields:
        return find_job_by_id(db, job_id)
    db.jobs.update_one({"_id": job_id}, {"$set": fields})
    return find_job_by_id(db, job_id)


def count_questions_for_job(db: Database, job_id: str) -> int:
    return db.questions.count_documents({"job_id": job_id})


# --- Questions ---------------------------------------------------------------
def delete_questions_for_job(db: Database, job_id: str) -> None:
    db.questions.delete_many({"job_id": job_id})


def insert_questions(db: Database, job_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    docs = [{"job_id": job_id, **row} for row in rows]
    result = db.questions.insert_many(docs)
    return len(result.inserted_ids)


def list_questions_for_job(db: Database, job_id: str) -> list[Question]:
    cursor = db.questions.find({"job_id": job_id}).sort("_id", 1)
    return [_question_from_doc(doc) for doc in cursor]


def find_question_by_id(db: Database, question_id: str) -> Question | None:
    try:
        oid = ObjectId(question_id)
    except (InvalidId, TypeError):
        return None
    doc = db.questions.find_one({"_id": oid})
    return _question_from_doc(doc) if doc else None


def update_question(db: Database, question_id: str, **fields: Any) -> Question | None:
    try:
        oid = ObjectId(question_id)
    except (InvalidId, TypeError):
        return None
    if fields:
        db.questions.update_one({"_id": oid}, {"$set": fields})
    doc = db.questions.find_one({"_id": oid})
    return _question_from_doc(doc) if doc else None
