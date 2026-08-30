# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SQLITE_DEFAULT = f"sqlite:///{str(BASE_DIR / 'pulseops.db').replace(os.sep, '/')}"


def _normalize_db_url(url: str) -> str:
    """Force the psycopg (v3) driver for PostgreSQL so the app is portable
    between Supabase (PostgreSQL) and the local SQLite development default.

    Only real database URLs are accepted. Anything else (e.g. a pasted
    Supabase project URL starting with https://) is ignored so the app still
    boots on the local SQLite dev database instead of crashing."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("sqlite://"):
        return url
    print(f"[config] WARNING: unsupported DATABASE_URL scheme ('{url.split('://', 1)[0]}://'), "
          f"falling back to local SQLite dev DB: {SQLITE_DEFAULT}")
    return SQLITE_DEFAULT


class Settings:
    """Runtime configuration. All secrets are read from backend/.env only —
    nothing is ever exposed through the API."""

    def __init__(self):
        self.app_name = os.getenv("APP_NAME", "AI Payment Operations Agent")
        self.app_version = os.getenv("APP_VERSION", "1.0.0")
        self.database_url = _normalize_db_url(os.getenv("DATABASE_URL", "") or SQLITE_DEFAULT)

        # Gateways / providers (test mode by default)
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.razorpay_webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        self.razorpay_api_base = os.getenv("RAZORPAY_API_BASE", "https://api.razorpay.com/v1")

        # AI operations agent
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_api_base = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")

        # Anomaly detection: minimum failed transactions in the window before a
        # spike is created. Kept small (default 2) so the local test-mode flow
        # produces a visible spike immediately; override via ANOMALY_MIN_TRANSACTIONS.
        self.anomaly_min_transactions = max(
            1, int(os.getenv("ANOMALY_MIN_TRANSACTIONS", "2") or 2)
        )

        # CORS
        raw = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173,http://localhost:3000")
        self.frontend_origins = [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def webhook_configured(self) -> bool:
        return bool(self.razorpay_webhook_secret)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()