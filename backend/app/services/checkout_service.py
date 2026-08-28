from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import CheckoutEvent, CheckoutSession
from ..utils.helpers import now_utc

VALID_EVENT_TYPES = {
    "checkout_started",
    "payment_method_selected",
    "payment_initiated",
    "otp_started",
    "otp_failed",
    "otp_completed",
    "payment_completed",
    "checkout_abandoned",
    "checkout_closed",
    "payment_retry",
    "payment_method_switched",
}

TERMINAL_TYPES = {"payment_completed", "checkout_abandoned", "checkout_closed"}


class CheckoutError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _parse_ts(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def ingest_session_events(db: Session, events: list[dict]) -> dict:
    accepted = 0
    duplicates = 0
    rejected = 0

    for ev in events:
        if not isinstance(ev, dict):
            rejected += 1
            continue
        event_type = (ev.get("event_type") or ev.get("type") or "").strip()
        session_id = (ev.get("session_id") or ev.get("session") or "").strip()
        if event_type not in VALID_EVENT_TYPES or not session_id:
            rejected += 1
            continue

        event_id = ev.get("event_id") or ev.get("id")
        if event_id:
            existing = db.query(CheckoutEvent).filter(CheckoutEvent.event_id == event_id).first()
            if existing:
                duplicates += 1
                continue

        occurred_at = _parse_ts(ev.get("occurred_at") or ev.get("timestamp")) or now_utc()

        db.add(CheckoutEvent(
            event_id=event_id,
            session_id=session_id,
            event_type=event_type,
            method=ev.get("method"),
            error_code=ev.get("error_code"),
            error_reason=ev.get("error_reason"),
            payload=ev,
            created_at=occurred_at,
        ))

        session = db.query(CheckoutSession).filter(CheckoutSession.session_id == session_id).first()
        if session is None:
            session = CheckoutSession(
                session_id=session_id,
                order_id=ev.get("order_id"),
                device=ev.get("device"),
                status="active",
                started_at=occurred_at,
            )
            db.add(session)
            db.flush()

        if ev.get("order_id"):
            session.order_id = ev.get("order_id") or session.order_id
        if ev.get("device"):
            session.device = ev.get("device") or session.device
        if ev.get("method"):
            session.method = ev.get("method") or session.method

        # keep the session open on retry, otherwise mirror lifecycle state
        if event_type == "payment_retry":
            session.retry_count = (session.retry_count or 0) + 1

        if event_type == "payment_method_selected" and ev.get("method"):
            session.method = ev.get("method")

        if event_type == "payment_completed":
            if ev.get("payment_id"):
                session.payment_id = ev.get("payment_id")
            session.status = "completed"
            session.ended_at = occurred_at
            start = session.started_at or occurred_at
            session.duration_seconds = int(
                (occurred_at - start.replace(tzinfo=timezone.utc)).total_seconds()
            ) if start.tzinfo else None

        if event_type in ("checkout_abandoned", "checkout_closed"):
            session.status = "abandoned" if event_type == "checkout_abandoned" else session.status
            session.ended_at = occurred_at
            start = session.started_at or occurred_at
            session.duration_seconds = int(
                (occurred_at - start.replace(tzinfo=timezone.utc)).total_seconds()
            ) if start.tzinfo else None

        accepted += 1

    db.commit()
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def close_stale_sessions(db: Session, timeout_minutes: int = 30) -> int:
    cutoff = now_utc()
    try:
        from datetime import timedelta

        cutoff = cutoff - timedelta(minutes=timeout_minutes)
    except Exception:
        return 0
    sessions = (
        db.query(CheckoutSession)
        .filter(CheckoutSession.status == "active", CheckoutSession.started_at < cutoff)
        .all()
    )
    for s in sessions:
        s.status = "abandoned"
        s.ended_at = s.ended_at or now_utc()
        if s.started_at and s.ended_at:
            s.duration_seconds = int((s.ended_at - s.started_at).total_seconds())
    db.commit()
    return len(sessions)