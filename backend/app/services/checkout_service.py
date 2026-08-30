# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import CheckoutEvent, CheckoutSession
from ..utils.helpers import now_utc
from .serializers import payment_status_from_rzp

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
                (occurred_at - (start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start)).total_seconds()
            )

        if event_type in ("checkout_abandoned", "checkout_closed"):
            session.status = "abandoned" if event_type == "checkout_abandoned" else session.status
            session.ended_at = occurred_at
            start = session.started_at or occurred_at
            session.duration_seconds = int(
                (occurred_at - (start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start)).total_seconds()
            )

        accepted += 1

    db.commit()
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def _append_event(
    db: Session, *, session_id: str, event_type: str, event_id: str,
    method: str | None = None, error_code: str | None = None,
    error_reason: str | None = None, occurred_at=None,
) -> bool:
    """Idempotently add a CheckoutEvent (keyed by event_id). Returns True if added."""
    if db.query(CheckoutEvent).filter(CheckoutEvent.event_id == event_id).first() is not None:
        return False
    db.add(CheckoutEvent(
        event_id=event_id,
        session_id=session_id,
        event_type=event_type,
        method=method,
        error_code=error_code,
        error_reason=error_reason,
        created_at=occurred_at or now_utc(),
    ))
    return True


def record_order_started(db: Session, order_id: str, *, device: str | None = None) -> None:
    """Backend-derived checkout_started signal — emitted when we issue a real
    Razorpay Order for the SDK checkout. Idempotent per order."""
    if not order_id:
        return
    session_id = str(order_id)
    session = db.query(CheckoutSession).filter(CheckoutSession.session_id == session_id).first()
    if session is None:
        session = CheckoutSession(
            session_id=session_id,
            order_id=str(order_id),
            device=device,
            status="active",
            started_at=now_utc(),
        )
        db.add(session)
        db.flush()

    _append_event(
        db, session_id=session_id, event_type="checkout_started",
        event_id=f"checkout_started:{session_id}:init",
    )
    db.commit()


def _looks_like_otp_failure(error_code: str | None, error_reason: str | None) -> bool:
    hint = f"{(error_code or '').lower()} {(error_reason or '').lower()}"
    return "otp" in hint or any(k in hint for k in ("pin", "bad_otp", "otp_expired", "incorrect_otp"))


def record_payment_outcome(
    db: Session,
    order_id: str | None,
    entity: dict,
    status: str | None = None,
) -> None:
    """Derive checkout funnel telemetry from REAL payment activity.

    Every payment that flows through our checkout (order_id present) produces a
    consistent funnel: payment_method_selected -> payment_initiated ->
    payment_completed | (otp_started/otp_failed | payment_retry on failure).
    Nothing here is fabricated — the events are derived from the actual payment
    entity persisted from Razorpay.
    """
    if not order_id:
        return
    session_id = str(order_id)
    session = db.query(CheckoutSession).filter(CheckoutSession.session_id == session_id).first()
    now = now_utc()
    if session is None:
        session = CheckoutSession(session_id=session_id, order_id=str(order_id), status="active", started_at=now)
        db.add(session)
        db.flush()

    pid = entity.get("id")
    method = entity.get("method")
    status = status or payment_status_from_rzp(entity.get("status"))
    error_code = entity.get("error_code")
    error_reason = entity.get("error_description")

    # payment_method_selected: first method we've observed for this session
    if method and not session.method:
        _append_event(
            db, session_id=session_id, event_type="payment_method_selected",
            event_id=f"payment_method_selected:{session_id}:{method}", method=method,
        )
        session.method = method

    _append_event(
        db, session_id=session_id, event_type="payment_initiated",
        event_id=f"payment_initiated:{session_id}:{pid or 'x'}",
        method=method, error_code=error_code, error_reason=error_reason,
    )

    if status in ("captured", "authorized", "success"):
        _append_event(
            db, session_id=session_id, event_type="payment_completed",
            event_id=f"payment_completed:{session_id}:{pid}",
            method=method,
        )
        if pid:
            session.payment_id = pid
        session.status = "completed"
        session.ended_at = now
    else:
        if _looks_like_otp_failure(error_code, error_reason):
            _append_event(
                db, session_id=session_id, event_type="otp_started",
                event_id=f"otp_started:{session_id}:{pid or 'x'}",
                method=method, error_code=error_code, error_reason=error_reason,
            )
            _append_event(
                db, session_id=session_id, event_type="otp_failed",
                event_id=f"otp_failed:{session_id}:{pid or 'x'}",
                method=method, error_code=error_code, error_reason=error_reason,
            )
        # retry = another payment attempt already recorded for this session
        earlier = (
            db.query(CheckoutEvent)
            .filter(
                CheckoutEvent.session_id == session_id,
                CheckoutEvent.event_type == "payment_initiated",
            )
            .count()
        )
        if earlier > 1:
            _append_event(
                db, session_id=session_id, event_type="payment_retry",
                event_id=f"payment_retry:{session_id}:{pid or 'x'}",
                method=method, error_code=error_code, error_reason=error_reason,
            )
            session.retry_count = (session.retry_count or 0) + 1

    if session.started_at and session.ended_at:
        try:
            session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
        except (TypeError, ValueError):
            pass

    db.commit()


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