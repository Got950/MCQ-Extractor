"""Security + sanitisation helpers shared across the API."""

from __future__ import annotations

import re
from typing import AsyncIterator, Iterable

import bleach
from fastapi import HTTPException, UploadFile, status

from config import settings

MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024
ALLOWED_PDF_MIME = {"application/pdf", "application/x-pdf"}
PDF_MAGIC = b"%PDF-"

ALLOWED_TAGS_RICH: list[str] = ["br"]
ALLOWED_TAGS_PLAIN: list[str] = []
ALLOWED_ATTRS: dict[str, list[str]] = {}


def clean_rich(value: str | None) -> str:
    """Strip everything except <br>. Used for question_text + solution."""
    if not value:
        return ""
    return bleach.clean(
        value, tags=ALLOWED_TAGS_RICH, attributes=ALLOWED_ATTRS, strip=True
    )


def clean_plain(value: str | None) -> str:
    """Strip all HTML. Used for option text and other short user fields."""
    if not value:
        return ""
    return bleach.clean(
        value, tags=ALLOWED_TAGS_PLAIN, attributes=ALLOWED_ATTRS, strip=True
    )


def clean_many(values: Iterable[str | None]) -> list[str]:
    return [clean_plain(v) for v in values]


def assert_pdf_mime(file: UploadFile) -> None:
    if (file.content_type or "").lower() not in ALLOWED_PDF_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are allowed",
        )
    name = (file.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must end with .pdf",
        )


async def validated_chunks(
    file: UploadFile, chunk_size: int = 1024 * 1024
) -> AsyncIterator[bytes]:
    """Async generator that yields validated chunks from ``file``.

    - First chunk must start with ``%PDF-``.
    - Total bytes must stay under :data:`MAX_UPLOAD_BYTES`.
    Raises ``HTTPException`` early if either rule is violated.
    """
    total = 0
    first = True
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        if first:
            if not chunk.startswith(PDF_MAGIC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is not a valid PDF",
                )
            first = False
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {settings.max_upload_mb} MB limit",
            )
        yield chunk


_SAFE_SUBJECTS = {"Physics", "Chemistry", "Mathematics"}


def validate_subject(value: str) -> str:
    value = (value or "").strip()
    if value not in _SAFE_SUBJECTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subject"
        )
    return value


_SAFE_PROVIDERS = {"gemini", "ollama"}


def validate_provider(value: str, available: dict[str, bool]) -> str:
    value = (value or "").strip().lower()
    if value not in _SAFE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider"
        )
    if not available.get(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{value}' is not configured on the server",
        )
    return value


_LANGUAGE_RE = re.compile(r"^[A-Za-z\s\-]{1,32}$")


def validate_language(value: str | None) -> str:
    if not value:
        return "English"
    value = value.strip()
    if not _LANGUAGE_RE.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid language"
        )
    return value
