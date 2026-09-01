from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns introduced for auth/RBAC that must be added in place to databases
# created before this change (create_all won't ADD columns to existing tables).
_ADDITIONS = {
    "payments": ["merchant_id"],
    "payment_events": ["merchant_id"],
    "payment_attempts": ["merchant_id"],
    "upi_mandates": ["merchant_id"],
    "mandate_events": ["merchant_id"],
    "checkout_sessions": ["merchant_id"],
    "checkout_events": ["merchant_id"],
    "anomalies": ["merchant_id"],
    "ai_decisions": ["user_id", "merchant_id"],
    "recovery_actions": ["merchant_id", "approved_by_user_id", "approved_at", "executed_by_user_id"],
    "recovery_outcomes": ["executed_by_user_id", "merchant_id"],
    "audit_logs": ["user_id", "actor_role", "merchant_id"],
    "daily_reports": ["merchant_id"],
}

# Drop-in column type definitions, portable across SQLite and PostgreSQL.
_COLUMN_TYPES = {
    "merchant_id": "VARCHAR(64)",
    "user_id": "VARCHAR(64)",
    "actor_role": "VARCHAR(24)",
    "approved_by_user_id": "VARCHAR(64)",
    "executed_by_user_id": "VARCHAR(64)",
    "approved_at": "TIMESTAMP",
}


def _migrate_columns(engine):
    """Idempotently add auth/RBAC columns to existing databases in place,
    preserving all stored demo data. Works for both the local SQLite dev DB and
    Supabase PostgreSQL. Backfills the shared demo merchant into older rows."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
        with engine.connect() as conn:
            for table, cols in _ADDITIONS.items():
                try:
                    existing = {c["name"] for c in insp.get_columns(table)}
                except Exception:  # noqa: BLE001 - table may not exist yet
                    continue
                for col in cols:
                    if col in existing:
                        continue
                    conn.execute(
                        text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {_COLUMN_TYPES[col]}')
                    )

            # Backfill the shared demo merchant into older rows (single-merchant demo).
            m = settings.demo_merchant_id
            for table in _ADDITIONS:
                try:
                    conn.execute(
                        text(f'UPDATE "{table}" SET merchant_id = :m WHERE merchant_id IS NULL'),
                        {"m": m},
                    )
                except Exception:  # noqa: BLE001
                    continue
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"[init_db] column migration skipped: {exc}")


def init_db():
    from . import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrate_columns(engine)