"""Centralised runtime configuration.

All env vars are read once here so the rest of the codebase imports a single
``settings`` object. Keeps the surface small and the dependency direction clean.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None and value != "" else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- Core ---------------------------------------------------------------
    app_secret: str
    allowed_origins: list[str]
    environment: str

    # --- Database (MongoDB Atlas) -------------------------------------------
    mongodb_uri: str
    mongodb_db_name: str

    # --- Superadmin (seeded via scripts.init_database) ------------------------
    superadmin_email: str | None
    superadmin_password: str | None
    superadmin_max_uploads: int

    # --- Auth ---------------------------------------------------------------
    jwt_algorithm: str
    jwt_expire_minutes: int

    # --- Job queue ----------------------------------------------------------
    redis_url: str | None
    queue_name: str

    # --- Storage ------------------------------------------------------------
    upload_dir: Path
    s3_bucket: str | None
    s3_region: str | None
    s3_endpoint: str | None  # for MinIO / local S3 compatibles

    # --- Retention / cleanup -----------------------------------------------
    upload_ttl_hours: int

    # --- LLM providers ------------------------------------------------------
    gemini_api_key: str | None
    ollama_host: str | None
    ollama_model: str

    # --- Limits -------------------------------------------------------------
    max_upload_mb: int
    max_uploads_per_user: int

    @property
    def use_redis(self) -> bool:
        return bool(self.redis_url)

    @property
    def use_s3(self) -> bool:
        return bool(self.s3_bucket)

    def providers(self) -> dict[str, bool]:
        return {
            "gemini": bool(self.gemini_api_key),
            "ollama": bool(self.ollama_host),
        }


def _resolve_gemini_primary_key() -> str | None:
    """Pick the first available Gemini key for the providers() health check.

    Prefers ``GEMINI_API_KEY``; otherwise falls back to the first entry of the
    comma-separated ``GEMINI_API_KEYS`` rotation list.
    """
    single = os.environ.get("GEMINI_API_KEY")
    if single and single.strip():
        return single.strip()
    multi = os.environ.get("GEMINI_API_KEYS", "")
    for k in multi.split(","):
        k = k.strip()
        if k:
            return k
    return None


def load_settings() -> Settings:
    allowed_origin = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")
    origins = [o.strip() for o in allowed_origin.split(",") if o.strip()]

    upload_dir = Path(
        os.environ.get("UPLOAD_DIR", PROJECT_ROOT / "uploads")
    ).resolve()

    return Settings(
        app_secret=os.environ.get("APP_SECRET", "change-me-in-prod"),
        allowed_origins=origins,
        environment=os.environ.get("ENVIRONMENT", "dev"),
        mongodb_uri=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_db_name=os.environ.get("MONGODB_DB_NAME", "mcq_extractor"),
        superadmin_email=(os.environ.get("SUPERADMIN_EMAIL") or "").strip() or None,
        superadmin_password=(os.environ.get("SUPERADMIN_PASSWORD") or "").strip() or None,
        superadmin_max_uploads=_int(os.environ.get("SUPERADMIN_MAX_UPLOADS"), 100),
        jwt_algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=_int(os.environ.get("JWT_EXPIRE_MINUTES"), 60 * 24),
        redis_url=os.environ.get("REDIS_URL") or None,
        queue_name=os.environ.get("QUEUE_NAME", "mcq-extractor"),
        upload_dir=upload_dir,
        s3_bucket=os.environ.get("S3_BUCKET") or None,
        s3_region=os.environ.get("S3_REGION") or None,
        s3_endpoint=os.environ.get("S3_ENDPOINT") or None,
        upload_ttl_hours=_int(os.environ.get("UPLOAD_TTL_HOURS"), 24 * 7),
        gemini_api_key=_resolve_gemini_primary_key(),
        ollama_host=os.environ.get("OLLAMA_HOST") or None,
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5vl"),
        max_upload_mb=_int(os.environ.get("MAX_UPLOAD_MB"), 50),
        max_uploads_per_user=_int(os.environ.get("MAX_UPLOADS_PER_USER"), 1),
    )


settings = load_settings()
