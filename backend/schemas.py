from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

Subject = Literal["Physics", "Chemistry", "Mathematics"]
Provider = Literal["gemini", "ollama"]
JobStatus = Literal["pending", "queued", "processing", "done", "failed"]
CorrectAnswer = Literal["A", "B", "C", "D"]
QuestionSubject = Literal["Physics", "Chemistry", "Mathematics", "General"]
VALID_QUESTION_SUBJECTS = frozenset({"Physics", "Chemistry", "Mathematics", "General"})


# --- Auth -------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime
    is_superadmin: bool = False
    upload_count: int = 0


# --- LLM providers ----------------------------------------------------------
class ProvidersOut(BaseModel):
    gemini: bool
    ollama: bool


# --- Upload + jobs ----------------------------------------------------------
class UploadResponse(BaseModel):
    id: str


class JobOut(BaseModel):
    id: str
    subject: str
    language: str
    provider: str
    status: JobStatus
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    question_count: int = 0
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    progress_label: Optional[str] = None

    class Config:
        from_attributes = True


class QuestionOut(BaseModel):
    id: str
    job_id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: Optional[CorrectAnswer] = None
    solution: str = ""
    subject: str = "General"

    @classmethod
    def from_question(cls, q) -> "QuestionOut":
        return cls(
            id=q.id,
            job_id=q.job_id,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_answer=q.correct_answer,
            solution=q.solution,
            subject=q.subject,
        )


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(default=None)
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_answer: Optional[CorrectAnswer] = None
    solution: Optional[str] = None
    subject: Optional[str] = None

    @field_validator("subject")
    @classmethod
    def subject_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_QUESTION_SUBJECTS:
            raise ValueError(
                "subject must be Physics, Chemistry, Mathematics, or General"
            )
        return v


# --- Health -----------------------------------------------------------------
class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class ReadyOut(BaseModel):
    ready: bool
    checks: dict[str, bool]


# --- Cleanup ----------------------------------------------------------------
class CleanupResult(BaseModel):
    deleted: int
    cutoff_hours: int
