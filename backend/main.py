"""FastAPI entrypoint: routes, auth, rate-limiting."""

import logging
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.database import Database
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from auth import create_access_token, get_current_user, hash_password, verify_password
from config import settings
from database import ensure_database, get_db, ping_db
from job_progress import get_progress
from job_stale import reconcile_stale_job
from job_queue import enqueue_extraction, ping_queue
from models import Job, User
from repos import (
    count_jobs_for_user,
    count_questions_for_job,
    create_job,
    create_user,
    delete_questions_for_job,
    find_job_by_id,
    find_question_by_id,
    find_user_by_email,
    list_jobs_for_user,
    list_questions_for_job,
    update_job,
    update_question,
)
from schemas import (
    CleanupResult,
    HealthOut,
    JobOut,
    LoginIn,
    ProvidersOut,
    QuestionOut,
    QuestionUpdate,
    ReadyOut,
    RegisterIn,
    TokenOut,
    UploadResponse,
    UserOut,
)
from security import (
    assert_pdf_mime,
    clean_plain,
    clean_rich,
    validate_language,
    validate_provider,
    validate_subject,
    validated_chunks,
)
from storage import get_storage

logger = logging.getLogger("mcq-extractor")
logging.basicConfig(level=logging.INFO)

APP_VERSION = "1.2.1"


limiter = Limiter(key_func=get_remote_address, default_limits=[])

app = FastAPI(title="MCQ Extractor", version=APP_VERSION)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
_cors_kwargs: dict = {
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["*"],
    "allow_credentials": False,
}
if settings.environment == "production":
    # Explicit ALLOWED_ORIGIN plus any Netlify site / branch preview URL.
    _cors_kwargs["allow_origins"] = settings.allowed_origins
    _cors_kwargs["allow_origin_regex"] = r"https://([a-z0-9-]+\.)*netlify\.app"
else:
    _cors_kwargs["allow_origins"] = settings.allowed_origins or ["*"]

app.add_middleware(CORSMiddleware, **_cors_kwargs)

ensure_database()
logger.info(
    "Backend up. DB=mongodb, storage=%s, queue=%s, cors_origins=%s",
    "s3" if settings.use_s3 else "local",
    "redis" if settings.use_redis else "inproc",
    settings.allowed_origins,
)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests. Try again in a minute."},
    )


@app.exception_handler(Exception)
async def _generic_error_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    return HealthOut(version=APP_VERSION)


@app.get("/api/ready", response_model=ReadyOut, tags=["health"])
def ready() -> ReadyOut:
    checks = {"db": ping_db(), "queue": ping_queue()}
    return ReadyOut(ready=all(checks.values()), checks=checks)


@app.get("/api/llm-providers", response_model=ProvidersOut, tags=["public"])
def llm_providers() -> ProvidersOut:
    return ProvidersOut(**settings.providers())


@app.post("/api/auth/register", response_model=TokenOut, tags=["auth"])
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterIn, db: Database = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    if find_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        user = create_user(db, email=email, password_hash=hash_password(payload.password))
    except ValueError:
        raise HTTPException(status_code=400, detail="Email already registered")
    token = create_access_token(user.id, user.email)
    return TokenOut(access_token=token)


@app.post("/api/auth/login", response_model=TokenOut, tags=["auth"])
@limiter.limit("10/minute")
def login(request: Request, payload: LoginIn, db: Database = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    user = find_user_by_email(db, email)
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return TokenOut(access_token=token)


def _user_out(db: Database, user: User) -> UserOut:
    count = count_jobs_for_user(db, user.id)
    return UserOut(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_superadmin=user.is_superadmin,
        upload_count=count,
    )


def _get_owned_job_or_404(job_id: str, db: Database, user: User) -> Job:
    job = find_job_by_id(db, job_id)
    if not job or job.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _job_out(db: Database, job: Job) -> JobOut:
    job = reconcile_stale_job(db, job)
    count = (
        count_questions_for_job(db, job.id) if job.status == "done" else 0
    )
    prog = get_progress(job.id) if job.status in ("queued", "processing") else None
    return JobOut(
        id=job.id,
        subject=job.subject,
        language=job.language,
        provider=job.provider,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        question_count=count,
        progress_current=int(prog["current"]) if prog else None,
        progress_total=int(prog["total"]) if prog else None,
        progress_label=str(prog.get("label") or "") if prog else None,
    )


@app.get("/api/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(get_current_user), db: Database = Depends(get_db)) -> UserOut:
    return _user_out(db, user)


@app.post("/api/upload", response_model=UploadResponse, tags=["jobs"])
@limiter.limit("10/minute")
async def upload_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject: str = Form(...),
    language: str = Form("English"),
    provider: str = Form(...),
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    subject = validate_subject(subject)
    language = validate_language(language)
    provider = validate_provider(provider, settings.providers())
    assert_pdf_mime(file)

    job_id = uuid.uuid4().hex
    pdf_key = f"{job_id}.pdf"
    storage = get_storage()

    try:
        await _stream_to_storage(storage, pdf_key, file)
    except HTTPException:
        storage.delete(pdf_key)
        raise
    except Exception:
        storage.delete(pdf_key)
        logger.exception("Failed to store upload")
        raise HTTPException(status_code=500, detail="Could not store upload")

    create_job(
        db,
        job_id=job_id,
        owner_id=user.id,
        subject=subject,
        language=language,
        provider=provider,
        pdf_key=pdf_key,
        status="queued",
    )

    backend_used = enqueue_extraction(job_id, background_tasks)
    logger.info("Enqueued job %s via %s (user=%s)", job_id, backend_used, user.email)
    return UploadResponse(id=job_id)


async def _stream_to_storage(storage, key: str, file: UploadFile) -> None:
    chunks: list[bytes] = []
    async for chunk in validated_chunks(file):
        chunks.append(chunk)
    storage.write_stream(key, iter(chunks))


@app.get("/api/jobs", response_model=list[JobOut], tags=["jobs"])
def list_jobs(
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[JobOut]:
    jobs = list_jobs_for_user(db, user.id)
    return [_job_out(db, job) for job in jobs]


@app.get("/api/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
def get_job(
    job_id: str,
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    return _job_out(db, _get_owned_job_or_404(job_id, db, user))


@app.post("/api/jobs/{job_id}/retry", response_model=JobOut, tags=["jobs"])
@limiter.limit("10/minute")
def retry_job(
    request: Request,
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    job = _get_owned_job_or_404(job_id, db, user)
    if job.status not in ("failed", "done"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry job with status '{job.status}'",
        )

    delete_questions_for_job(db, job_id)
    update_job(
        db,
        job_id,
        status="queued",
        error_message=None,
        completed_at=None,
    )

    enqueue_extraction(job_id, background_tasks)
    logger.info("Retry enqueued for job %s (user=%s)", job_id, user.email)
    job = find_job_by_id(db, job_id)
    assert job is not None
    return _job_out(db, job)


@app.get(
    "/api/jobs/{job_id}/questions",
    response_model=list[QuestionOut],
    tags=["jobs"],
)
def get_questions(
    job_id: str,
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuestionOut]:
    _get_owned_job_or_404(job_id, db, user)
    rows = list_questions_for_job(db, job_id)
    return [QuestionOut.from_question(r) for r in rows]


@app.put(
    "/api/questions/{question_id}",
    response_model=QuestionOut,
    tags=["jobs"],
)
def update_question_route(
    question_id: str,
    payload: QuestionUpdate,
    db: Database = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuestionOut:
    q = find_question_by_id(db, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    _get_owned_job_or_404(q.job_id, db, user)

    fields: dict = {}
    if payload.question_text is not None:
        fields["question_text"] = clean_rich(payload.question_text)
    if payload.option_a is not None:
        fields["option_a"] = clean_plain(payload.option_a)
    if payload.option_b is not None:
        fields["option_b"] = clean_plain(payload.option_b)
    if payload.option_c is not None:
        fields["option_c"] = clean_plain(payload.option_c)
    if payload.option_d is not None:
        fields["option_d"] = clean_plain(payload.option_d)
    if payload.correct_answer is not None:
        fields["correct_answer"] = payload.correct_answer
    if payload.solution is not None:
        fields["solution"] = clean_rich(payload.solution)
    if payload.subject is not None:
        fields["subject"] = payload.subject

    try:
        updated = update_question(db, question_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionOut.from_question(updated)


@app.post("/api/maintenance/cleanup-uploads", response_model=CleanupResult, tags=["admin"])
def trigger_cleanup(
    user: User = Depends(get_current_user),
) -> CleanupResult:
    from tasks import cleanup_old_uploads

    deleted = cleanup_old_uploads()
    return CleanupResult(deleted=deleted, cutoff_hours=settings.upload_ttl_hours)
