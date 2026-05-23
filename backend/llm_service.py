"""Unified LLM interface for MCQ extraction.

Two providers, one entrypoint::

    extract_mcqs(pdf_path, subject, provider) -> list[dict]

Each provider receives the same prompt and must return a JSON object of the
shape ``{"questions": [...]}``. Math must be wrapped in ``\\( ... \\)`` and
multi-step solutions joined with literal ``<br>`` tags.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_CHUNK_PAGES = 1
DEFAULT_GEMINI_MAX_OUTPUT_TOKENS = 65536
DEFAULT_GEMINI_TIMEOUT_S = 75
DEFAULT_GEMINI_JOB_BUDGET_S = 85
DEFAULT_GEMINI_MAX_PAGES_SINGLE_SHOT = 30
DEFAULT_GEMINI_PARALLEL_WORKERS = 6
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_INITIAL_BACKOFF_S = 1.0
_DEFAULT_MAX_BACKOFF_S = 8.0

_throttle_lock = threading.Lock()
_last_call_ts = 0.0


class _GeminiOptions(TypedDict):
    A: str
    B: str
    C: str
    D: str


class _GeminiQuestion(TypedDict):
    question_text: str
    options: _GeminiOptions
    correct_answer: str
    solution: str


class _GeminiOutput(TypedDict):
    questions: list[_GeminiQuestion]


class GeminiMaxTokensError(RuntimeError):
    """Raised when a page range produces more JSON than the model can return."""

SHARED_PROMPT_TEMPLATE = """You are an expert academic content parser.

Extract EVERY multiple-choice question (MCQ) from the attached {subject} PDF.

Strict output rules:
1. Return ONLY raw JSON. No markdown fences. No preamble. No trailing prose.
2. Top-level shape:
{{
  "questions": [
    {{
      "question_text": "string",
      "options": {{"A": "string", "B": "string", "C": "string", "D": "string"}},
      "correct_answer": "A" | "B" | "C" | "D" | null,
      "solution": "string"
    }}
  ]
}}
CRITICAL JSON RULE: You are writing values inside a JSON string.
Every backslash MUST be doubled. Write \\\\( not \\(, write \\\\) not \\),
write \\\\frac not \\frac, write \\\\le not \\le, write \\\\ge not \\ge,
write \\\\times not \\times, write \\\\sqrt not \\sqrt, write \\\\pm not \\pm.
A single backslash inside a JSON string is always a syntax error.
3. Wrap ALL mathematical expressions in \\( ... \\). NEVER use $...$ or $$...$$.
   Plain words like "and", "therefore", "where" stay unwrapped.
4. Join multi-step solution lines with literal <br> HTML tags (no real newlines inside the solution string).
5. If a field is not present in the PDF, use null for correct_answer or "" for solution.
6. Do not merge or split questions. Each MCQ in the PDF = one entry.
7. Keep option text faithful to the source (preserve units, signs, math).
"""


def extract_mcqs(
    pdf_path: str,
    subject: str,
    provider: str,
    job_id: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the configured LLM provider and return a list of question dicts."""
    provider = (provider or "").lower().strip()
    if provider == "gemini":
        return _call_gemini(pdf_path, subject, job_id=job_id)
    if provider == "ollama":
        return _call_ollama(pdf_path, subject)
    raise ValueError(f"Unknown provider: {provider!r}")


def _gemini_keys() -> list[str]:
    """Return all configured Gemini API keys, preferring ``GEMINI_API_KEYS``.

    ``GEMINI_API_KEYS`` may be a comma-separated list. ``GEMINI_API_KEY`` is
    kept as a single-key fallback so existing deployments keep working.
    """
    multi = os.environ.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in multi.split(",") if k.strip()]
    if keys:
        return keys
    single = (os.environ.get("GEMINI_API_KEY") or "").strip()
    return [single] if single else []


def _gemini_model_name() -> str:
    name = (os.environ.get("GEMINI_MODEL") or "").strip()
    return name or DEFAULT_GEMINI_MODEL


def _gemini_fallback_model_name() -> str | None:
    name = (os.environ.get("GEMINI_FALLBACK_MODEL") or "").strip()
    return name or None


def _gemini_chunk_pages() -> int:
    try:
        pages = int(os.environ.get("GEMINI_CHUNK_PAGES", str(DEFAULT_GEMINI_CHUNK_PAGES)))
    except ValueError:
        pages = DEFAULT_GEMINI_CHUNK_PAGES
    return max(1, pages)


def _gemini_job_budget_s() -> int:
    try:
        return max(30, int(os.environ.get("GEMINI_JOB_BUDGET_S", str(DEFAULT_GEMINI_JOB_BUDGET_S))))
    except ValueError:
        return DEFAULT_GEMINI_JOB_BUDGET_S


def _gemini_max_pages_single_shot() -> int:
    try:
        return max(1, int(os.environ.get("GEMINI_MAX_PAGES_SINGLE_SHOT", str(DEFAULT_GEMINI_MAX_PAGES_SINGLE_SHOT))))
    except ValueError:
        return DEFAULT_GEMINI_MAX_PAGES_SINGLE_SHOT


def _gemini_parallel_workers() -> int:
    try:
        return max(1, min(12, int(os.environ.get("GEMINI_PARALLEL_WORKERS", str(DEFAULT_GEMINI_PARALLEL_WORKERS)))))
    except ValueError:
        return DEFAULT_GEMINI_PARALLEL_WORKERS


def _check_job_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise RuntimeError(
            "Extraction exceeded the 90 second time limit. "
            "Try a shorter PDF or fewer pages per file."
        )


def _log_event(level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.log(level, "%s", payload)


def _gemini_throttle() -> None:
    """Enforce a minimum gap between Gemini calls, when configured.

    Set ``GEMINI_MIN_INTERVAL_MS`` (e.g. ``2500``) to cap effective RPM and
    avoid free-tier 429s. No-op when unset.
    """
    try:
        min_interval_ms = int(os.environ.get("GEMINI_MIN_INTERVAL_MS", "0"))
    except ValueError:
        min_interval_ms = 0
    if min_interval_ms <= 0:
        return
    global _last_call_ts
    with _throttle_lock:
        now = time.monotonic()
        wait = (_last_call_ts + min_interval_ms / 1000.0) - now
        if wait > 0:
            time.sleep(wait)
        _last_call_ts = time.monotonic()


def _is_retryable_gemini_error(exc: Exception) -> bool:
    """True for rate limits, gateway timeouts, and other transient Gemini failures."""
    try:
        from google.api_core import exceptions as gax_exceptions
    except ImportError:
        gax_exceptions = None  # type: ignore[assignment]

    if gax_exceptions is not None and isinstance(
        exc,
        (
            gax_exceptions.ResourceExhausted,
            gax_exceptions.ServiceUnavailable,
            gax_exceptions.DeadlineExceeded,
            gax_exceptions.GatewayTimeout,
            gax_exceptions.InternalServerError,
            gax_exceptions.Aborted,
        ),
    ):
        return True

    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "504",
            "503",
            "502",
            "429",
            "timed out",
            "timeout",
            "deadline exceeded",
            "unavailable",
            "gateway",
        )
    )


def _retry_delay_from_exc(exc: Exception, default: float) -> float:
    """Pull Google's suggested retry delay from a 429, else use ``default``."""
    delay = getattr(exc, "retry_delay", None)
    if delay is not None:
        seconds = getattr(delay, "seconds", None)
        if isinstance(seconds, (int, float)) and seconds > 0:
            return float(seconds) + 1.0
    match = re.search(r"retry in\s+([0-9.]+)\s*s", str(exc), re.IGNORECASE)
    if match:
        try:
            return float(match.group(1)) + 1.0
        except ValueError:
            pass
    return default


def _dedupe_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for q in questions:
        key = str(q.get("question_text", "") or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _gemini_request_config() -> tuple[int, int, int]:
    try:
        max_retries = int(
            os.environ.get("GEMINI_MAX_RETRIES", str(_DEFAULT_MAX_RETRIES))
        )
    except ValueError:
        max_retries = _DEFAULT_MAX_RETRIES
    max_retries = max(1, max_retries)

    try:
        timeout_s = int(
            os.environ.get("GEMINI_TIMEOUT_S", str(DEFAULT_GEMINI_TIMEOUT_S))
        )
    except ValueError:
        timeout_s = DEFAULT_GEMINI_TIMEOUT_S

    try:
        max_output_tokens = int(
            os.environ.get(
                "GEMINI_MAX_OUTPUT_TOKENS", str(DEFAULT_GEMINI_MAX_OUTPUT_TOKENS)
            )
        )
    except ValueError:
        max_output_tokens = DEFAULT_GEMINI_MAX_OUTPUT_TOKENS

    return max_retries, timeout_s, max_output_tokens


def _gemini_generate_chunk(
    *,
    pdf_b64: str,
    prompt: str,
    model_name: str,
    chunk_index: int,
    allow_fallback: bool = True,
    max_attempts: int | None = None,
) -> list[dict[str, Any]]:
    """Call Gemini for one PDF chunk with retries, key rotation, and optional fallback."""
    import google.generativeai as genai
    from google.api_core import exceptions as gax_exceptions

    keys = _gemini_keys()
    if not keys:
        raise RuntimeError("GEMINI_API_KEY (or GEMINI_API_KEYS) is not configured")

    max_retries, timeout_s, max_output_tokens = _gemini_request_config()
    if max_attempts is not None:
        max_retries = max(1, max_attempts)
    start_offset = random.randint(0, len(keys) - 1)
    last_exc: Exception | None = None
    quota_exhausted = False

    for attempt in range(max_retries):
        key_index = (start_offset + attempt) % len(keys)
        api_key = keys[key_index]
        try:
            _gemini_throttle()
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                [
                    {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                    {"text": prompt},
                ],
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                    "max_output_tokens": max_output_tokens,
                },
                request_options={"timeout": timeout_s},
            )
            _check_gemini_finish_reason(response)
            text = _extract_text_from_gemini_response(response)
            return _parse_questions(text)
        except gax_exceptions.ResourceExhausted as exc:
            last_exc = exc
            quota_exhausted = True
            backoff = min(
                _DEFAULT_INITIAL_BACKOFF_S * (2 ** attempt), _DEFAULT_MAX_BACKOFF_S
            )
            delay = _retry_delay_from_exc(exc, default=backoff)
            _log_event(
                logging.WARNING,
                "gemini_chunk_failed",
                chunk_index=chunk_index,
                error=str(exc),
                attempt=attempt + 1,
            )
            logger.warning(
                "Gemini 429 (attempt %d/%d, key #%d of %d) sleeping %.1fs",
                attempt + 1,
                max_retries,
                key_index + 1,
                len(keys),
                delay,
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
        except (
            gax_exceptions.ServiceUnavailable,
            gax_exceptions.DeadlineExceeded,
            gax_exceptions.GatewayTimeout,
            gax_exceptions.InternalServerError,
            gax_exceptions.Aborted,
        ) as exc:
            last_exc = exc
            backoff = min(
                _DEFAULT_INITIAL_BACKOFF_S * (2 ** attempt), _DEFAULT_MAX_BACKOFF_S
            )
            delay = _retry_delay_from_exc(exc, default=backoff)
            _log_event(
                logging.WARNING,
                "gemini_chunk_failed",
                chunk_index=chunk_index,
                error=str(exc),
                attempt=attempt + 1,
            )
            logger.warning(
                "Gemini transient %s (attempt %d/%d) sleeping %.1fs",
                exc.__class__.__name__,
                attempt + 1,
                max_retries,
                delay,
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
        except GeminiMaxTokensError:
            raise
        except Exception as exc:
            last_exc = exc
            if not _is_retryable_gemini_error(exc):
                raise
            backoff = min(
                _DEFAULT_INITIAL_BACKOFF_S * (2 ** attempt), _DEFAULT_MAX_BACKOFF_S
            )
            delay = _retry_delay_from_exc(exc, default=backoff)
            _log_event(
                logging.WARNING,
                "gemini_chunk_failed",
                chunk_index=chunk_index,
                error=str(exc),
                attempt=attempt + 1,
            )
            logger.warning(
                "Gemini retryable error (attempt %d/%d) sleeping %.1fs: %s",
                attempt + 1,
                max_retries,
                delay,
                exc,
            )
            if attempt < max_retries - 1:
                time.sleep(delay)

    assert last_exc is not None

    fallback_model = _gemini_fallback_model_name() if allow_fallback else None
    if quota_exhausted and allow_fallback and fallback_model and fallback_model != model_name:
        _log_event(
            logging.WARNING,
            "gemini_fallback_triggered",
            original_model=model_name,
            fallback_model=fallback_model,
            chunk_index=chunk_index,
        )
        try:
            return _gemini_generate_chunk(
                pdf_b64=pdf_b64,
                prompt=prompt,
                model_name=fallback_model,
                chunk_index=chunk_index,
                allow_fallback=False,
                max_attempts=1,
            )
        except gax_exceptions.ResourceExhausted as exc:
            raise RuntimeError(
                f"Gemini fallback model also exhausted: {exc}"
            ) from exc

    raise RuntimeError(f"Gemini exhausted retries: {last_exc}") from last_exc


def _gemini_extract_page_range(
    doc: Any,
    *,
    start: int,
    end: int,
    total_pages: int,
    subject: str,
    model_name: str,
    chunk_index: int,
) -> list[dict[str, Any]]:
    """Extract MCQs from inclusive page indices ``start``..``end`` (0-based)."""
    import pymupdf as fitz

    pages_label = f"{start + 1}-{end + 1}"
    base_prompt = SHARED_PROMPT_TEMPLATE.format(subject=subject)

    _log_event(
        logging.INFO,
        "gemini_chunk_started",
        chunk_index=chunk_index,
        pages=pages_label,
    )

    chunk_doc = fitz.open()
    try:
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end)
        chunk_bytes = chunk_doc.tobytes()
    finally:
        chunk_doc.close()

    chunk_b64 = base64.b64encode(chunk_bytes).decode("ascii")
    chunk_prompt = (
        f"{base_prompt}\n\n"
        f"This is pages {start + 1}–{end + 1} of a {total_pages}-page document.\n"
        "Extract only the MCQs that appear on these pages.\n"
        "Do not repeat questions from other chunks."
    )

    questions = _gemini_generate_chunk(
        pdf_b64=chunk_b64,
        prompt=chunk_prompt,
        model_name=model_name,
        chunk_index=chunk_index,
    )
    _log_event(
        logging.INFO,
        "gemini_chunk_done",
        chunk_index=chunk_index,
        pages=pages_label,
        questions_found=len(questions),
    )
    return questions


def _gemini_extract_with_split(
    doc: Any,
    *,
    start: int,
    end: int,
    total_pages: int,
    subject: str,
    model_name: str,
    chunk_index: int,
) -> list[dict[str, Any]]:
    """Try a page range; on output token overflow, bisect and merge."""
    try:
        return _gemini_extract_page_range(
            doc,
            start=start,
            end=end,
            total_pages=total_pages,
            subject=subject,
            model_name=model_name,
            chunk_index=chunk_index,
        )
    except GeminiMaxTokensError:
        if start >= end:
            raise RuntimeError(
                f"Page {start + 1} alone exceeds Gemini output limits. "
                "Try a shorter PDF section or fewer questions per page."
            ) from None
        mid = (start + end) // 2
        _log_event(
            logging.INFO,
            "gemini_chunk_split",
            pages=f"{start + 1}-{end + 1}",
            split_at=mid + 1,
        )
        left = _gemini_extract_with_split(
            doc,
            start=start,
            end=mid,
            total_pages=total_pages,
            subject=subject,
            model_name=model_name,
            chunk_index=chunk_index,
        )
        right = _gemini_extract_with_split(
            doc,
            start=mid + 1,
            end=end,
            total_pages=total_pages,
            subject=subject,
            model_name=model_name,
            chunk_index=chunk_index,
        )
        return left + right


def _gemini_extract_full_document(
    doc: Any,
    *,
    total_pages: int,
    subject: str,
    model_name: str,
) -> list[dict[str, Any]]:
    """One API call for the entire PDF (fastest path, target 20–90s)."""
    base_prompt = SHARED_PROMPT_TEMPLATE.format(subject=subject)
    pdf_b64 = base64.b64encode(doc.tobytes()).decode("ascii")
    prompt = (
        f"{base_prompt}\n\n"
        f"The attached PDF has {total_pages} page(s). "
        "Extract every MCQ in the document in a single JSON response."
    )
    _log_event(logging.INFO, "gemini_single_shot_started", pages=total_pages)
    questions = _gemini_generate_chunk(
        pdf_b64=pdf_b64,
        prompt=prompt,
        model_name=model_name,
        chunk_index=0,
    )
    _log_event(
        logging.INFO,
        "gemini_single_shot_done",
        pages=total_pages,
        questions_found=len(questions),
    )
    return questions


def _page_pdf_b64(doc: Any, start: int, end: int) -> str:
    import pymupdf as fitz

    chunk_doc = fitz.open()
    try:
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end)
        return base64.b64encode(chunk_doc.tobytes()).decode("ascii")
    finally:
        chunk_doc.close()


def _gemini_call_b64(
    *,
    pdf_b64: str,
    start: int,
    end: int,
    total_pages: int,
    subject: str,
    model_name: str,
    chunk_index: int,
) -> list[dict[str, Any]]:
    base_prompt = SHARED_PROMPT_TEMPLATE.format(subject=subject)
    chunk_prompt = (
        f"{base_prompt}\n\n"
        f"This is pages {start + 1}–{end + 1} of a {total_pages}-page document.\n"
        "Extract only the MCQs that appear on these pages.\n"
        "Do not repeat questions from other chunks."
    )
    return _gemini_generate_chunk(
        pdf_b64=pdf_b64,
        prompt=chunk_prompt,
        model_name=model_name,
        chunk_index=chunk_index,
    )


def _gemini_parallel_page_extract(
    doc: Any,
    *,
    total_pages: int,
    subject: str,
    model_name: str,
    job_id: str | None,
    deadline: float,
) -> list[dict[str, Any]]:
    """Fallback: one page per worker in parallel (still within ~90s budget)."""
    from job_progress import set_progress

    workers = min(_gemini_parallel_workers(), total_pages)
    _log_event(
        logging.INFO,
        "gemini_parallel_started",
        pages=total_pages,
        workers=workers,
    )

    page_b64 = [_page_pdf_b64(doc, i, i) for i in range(total_pages)]

    def _run_page(page_i: int) -> list[dict[str, Any]]:
        _check_job_deadline(deadline)
        try:
            return _gemini_call_b64(
                pdf_b64=page_b64[page_i],
                start=page_i,
                end=page_i,
                total_pages=total_pages,
                subject=subject,
                model_name=model_name,
                chunk_index=page_i,
            )
        except GeminiMaxTokensError:
            return _gemini_extract_with_split(
                doc,
                start=page_i,
                end=page_i,
                total_pages=total_pages,
                subject=subject,
                model_name=model_name,
                chunk_index=page_i,
            )

    master: list[dict[str, Any]] = []
    done_count = 0
    last_exc: Exception | None = None
    any_ok = False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_page, page_i): page_i for page_i in range(total_pages)}
        for fut in as_completed(futures):
            page_i = futures[fut]
            try:
                questions = fut.result()
                any_ok = True
                master.extend(questions)
            except Exception as exc:
                last_exc = exc
                _log_event(
                    logging.WARNING,
                    "gemini_chunk_failed",
                    chunk_index=page_i,
                    pages=f"{page_i + 1}",
                    error=str(exc),
                )
            done_count += 1
            if job_id:
                set_progress(
                    job_id,
                    current=done_count,
                    total=total_pages,
                    label=f"Page {done_count}/{total_pages}",
                )

    if not any_ok and last_exc is not None:
        raise last_exc
    return master


def _call_gemini(
    pdf_path: str, subject: str, job_id: str | None = None
) -> list[dict[str, Any]]:
    import pymupdf as fitz

    from job_progress import set_progress

    model_name = _gemini_model_name()
    deadline = time.monotonic() + _gemini_job_budget_s()

    with fitz.open(pdf_path) as doc:
        total_pages = len(doc)
        _check_job_deadline(deadline)

        if job_id:
            set_progress(job_id, current=0, total=1, label="Starting")

        master: list[dict[str, Any]] = []

        # Fast path: entire PDF in one Gemini call (typical 20–90s).
        if total_pages <= _gemini_max_pages_single_shot():
            if job_id:
                set_progress(job_id, current=1, total=1, label="Full document")
            try:
                master = _gemini_extract_full_document(
                    doc,
                    total_pages=total_pages,
                    subject=subject,
                    model_name=model_name,
                )
            except (GeminiMaxTokensError, RuntimeError) as exc:
                if isinstance(exc, RuntimeError) and not _is_retryable_gemini_error(exc):
                    raise
                reason = (
                    "max_output_tokens"
                    if isinstance(exc, GeminiMaxTokensError)
                    else "timeout_or_transient"
                )
                _log_event(
                    logging.INFO,
                    "gemini_single_shot_split",
                    pages=total_pages,
                    reason=reason,
                    error=str(exc),
                )
                master = _gemini_parallel_page_extract(
                    doc,
                    total_pages=total_pages,
                    subject=subject,
                    model_name=model_name,
                    job_id=job_id,
                    deadline=deadline,
                )
        else:
            _log_event(
                logging.INFO,
                "gemini_large_pdf_parallel",
                pages=total_pages,
            )
            master = _gemini_parallel_page_extract(
                doc,
                total_pages=total_pages,
                subject=subject,
                model_name=model_name,
                job_id=job_id,
                deadline=deadline,
            )

    merged = _dedupe_questions(master)
    _log_event(
        logging.INFO,
        "gemini_extraction_complete",
        total_questions=len(merged),
        pages=total_pages,
    )
    return merged


def _check_gemini_finish_reason(response: Any) -> None:
    """Raise a descriptive error when Gemini truncated or refused the response.

    ``finish_reason`` codes (per the SDK proto):
      1 STOP        - normal completion
      2 MAX_TOKENS  - hit token cap; output is truncated
      3 SAFETY      - blocked by safety filters
      4 RECITATION  - blocked for reciting copyrighted content
      5 OTHER       - generic failure
    """
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason:
            raise RuntimeError(
                f"Gemini blocked the request (prompt_feedback={block_reason})."
            )
        return
    reason = getattr(candidates[0], "finish_reason", None)
    reason_value = getattr(reason, "value", reason)
    if reason_value in (2, "MAX_TOKENS"):
        raise GeminiMaxTokensError(
            "Gemini hit max_output_tokens before finishing. "
            "Splitting into smaller page ranges."
        )
    if reason_value in (3, "SAFETY", 4, "RECITATION"):
        raise RuntimeError(
            f"Gemini refused to return content (finish_reason={reason_value})."
        )


def _extract_text_from_gemini_response(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                return part.text
    raise RuntimeError("Gemini response did not contain text")


def _call_ollama(pdf_path: str, subject: str) -> list[dict[str, Any]]:
    import pymupdf as fitz  # PyMuPDF
    import requests

    host = os.environ.get("OLLAMA_HOST")
    if not host:
        raise RuntimeError("OLLAMA_HOST is not configured")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5vl")

    images: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("ascii"))

    prompt = SHARED_PROMPT_TEMPLATE.format(subject=subject)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": images,
            }
        ],
    }

    resp = requests.post(
        f"{host.rstrip('/')}/api/chat",
        json=payload,
        timeout=600,
    )
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content")
    if not content:
        raise RuntimeError("Ollama response missing message.content")
    return _parse_questions(content)


_UNAMBIGUOUS_JSON_ESCAPES = set('"\\/')
_AMBIGUOUS_JSON_ESCAPES = set("bfnrt")
_HEX_DIGITS = set("0123456789abcdefABCDEF")


def _escape_control_chars_in_strings(s: str) -> str:
    """Inside JSON string literals, escape raw control chars (``< 0x20``).

    JSON forbids unescaped control characters in strings. Some LLM outputs
    contain literal newlines, tabs, or carriage returns inside string values,
    which the standard parser rejects with ``Invalid control character``.
    """
    out: list[str] = []
    in_string = False
    escape_next = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
            continue
        if escape_next:
            escape_next = False
            out.append(ch)
            i += 1
            continue
        if ch == "\\":
            escape_next = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = False
            out.append(ch)
            i += 1
            continue
        code = ord(ch)
        if code < 0x20:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\b":
                out.append("\\b")
            elif ch == "\f":
                out.append("\\f")
            else:
                out.append(f"\\u{code:04x}")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _balance_braces(s: str) -> str:
    """Trim trailing garbage and close any unclosed braces/brackets.

    Useful when a response is truncated mid-output: we keep the longest valid
    prefix and append the missing closers so a parser can read what we have.
    """
    last_brace = max(s.rfind("}"), s.rfind("]"))
    if last_brace < 0:
        return s
    trimmed = s[: last_brace + 1]
    stack: list[str] = []
    in_string = False
    escape_next = False
    for ch in trimmed:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    closers = "".join("}" if c == "{" else "]" for c in reversed(stack))
    return trimmed + closers


def _fix_invalid_json_escapes(s: str) -> str:
    """Repair backslash escapes that LLMs commonly mishandle inside JSON.

    Two failure modes are fixed:

    1. ``\\(`` — a raw LaTeX inline-math delimiter. JSON only allows
       ``\\`` to precede one of ``" \\ / b f n r t u``, so ``\\(`` is
       parsed as an "Invalid \\escape".
    2. ``\\frac``, ``\\nabla``, ``\\beta``, ``\\tau``, ``\\rho`` — these
       *look* like valid JSON escapes (``\\f``, ``\\n``, ``\\b``, ``\\t``,
       ``\\r``) but the following alphabetic character is a strong signal
       that the LLM meant a LaTeX command name, not a control char.

    The function walks the text once. Inside a JSON string literal it:

    * keeps ``\\"``, ``\\\\``, and ``\\/`` as-is (unambiguous),
    * keeps a valid ``\\uXXXX`` Unicode escape as-is,
    * treats ``\\b \\f \\n \\r \\t`` as LaTeX (doubles the backslash)
      when followed by another letter, and as JSON control chars
      otherwise,
    * doubles the backslash for anything else (``\\(``, ``\\[``,
      ``\\sum``, ``\\sqrt`` …).
    """
    out: list[str] = []
    in_string = False
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = False
            out.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt in _UNAMBIGUOUS_JSON_ESCAPES:
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            if nxt == "u":
                hex_block = s[i + 2 : i + 6]
                if len(hex_block) == 4 and all(c in _HEX_DIGITS for c in hex_block):
                    out.append(ch)
                    out.append(nxt)
                    i += 2
                    continue
                out.append("\\\\")
                i += 1
                continue
            if nxt in _AMBIGUOUS_JSON_ESCAPES:
                follow = s[i + 2] if i + 2 < n else ""
                if follow.isalpha():
                    out.append("\\\\")
                    i += 1
                    continue
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            out.append("\\\\")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _loads_lenient(text: str) -> Any:
    """Parse JSON with progressively more aggressive repairs.

    Order of attempts:
      1. Raw ``json.loads``.
      2. Escape raw control chars inside strings.
      3. Repair invalid ``\\X`` escapes (LaTeX inside strings).
      4. Both repairs combined.
      5. Extract the outermost ``{...}`` slice; retry the above on it.
      6. Brace-balance a truncated tail; retry the above on it.

    Raises the original ``JSONDecodeError`` if every strategy fails.
    """
    candidates: list[str] = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    candidates.append(_balance_braces(text))

    transforms: list[tuple[str, Any]] = [
        ("raw", lambda s: s),
        ("ctrl-chars", _escape_control_chars_in_strings),
        ("escapes", _fix_invalid_json_escapes),
        ("ctrl+escapes", lambda s: _fix_invalid_json_escapes(
            _escape_control_chars_in_strings(s)
        )),
    ]

    first_exc: json.JSONDecodeError | None = None
    for candidate in candidates:
        for label, transform in transforms:
            try:
                return json.loads(transform(candidate))
            except json.JSONDecodeError as exc:
                if first_exc is None:
                    first_exc = exc
                logger.debug("JSON parse strategy %r failed: %s", label, exc)
    assert first_exc is not None
    raise first_exc


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Parse raw LLM JSON: strip fences, repair escapes, then decode.

    Applies repairs in order before ``json.loads``. Falls back to brace
    balancing and control-char repair via ``_loads_lenient`` when needed.
    Never returns ``None``; raises ``json.JSONDecodeError`` or ``ValueError``.
    """
    cleaned = _strip_markdown_fences(text)
    repaired = _fix_invalid_json_escapes(cleaned)
    try:
        data = json.loads(repaired)
    except json.JSONDecodeError:
        data = _loads_lenient(cleaned)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")
    return data


def _parse_questions(text: str) -> list[dict[str, Any]]:
    """Parse model output, tolerating fences, control chars, and bad escapes."""
    try:
        data = _parse_llm_json(text)
    except json.JSONDecodeError:
        cleaned = _strip_markdown_fences(text)
        logger.error("LLM output not JSON (first 500 chars): %s", cleaned[:500])
        raise

    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list):
        raise ValueError("LLM response missing 'questions' list")

    normalised: list[dict[str, Any]] = []
    for raw in questions:
        if not isinstance(raw, dict):
            continue
        options = raw.get("options") or {}
        if not isinstance(options, dict):
            options = {}
        correct = raw.get("correct_answer")
        if isinstance(correct, str):
            correct = correct.strip().upper()
            if correct not in {"A", "B", "C", "D"}:
                correct = None
        else:
            correct = None
        normalised.append(
            {
                "question_text": str(raw.get("question_text", "") or ""),
                "options": {
                    "A": str(options.get("A", "") or ""),
                    "B": str(options.get("B", "") or ""),
                    "C": str(options.get("C", "") or ""),
                    "D": str(options.get("D", "") or ""),
                },
                "correct_answer": correct,
                "solution": str(raw.get("solution", "") or ""),
            }
        )
    return normalised
