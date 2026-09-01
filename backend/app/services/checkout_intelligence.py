from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import CheckoutEvent, CheckoutSession, Payment
from ..utils.helpers import calendar_days, iso, resolve_range, to_float

SUCCESS_PAYMENT_STATUSES = {"success", "captured", "authorized"}
FAILED_PAYMENT_STATUSES = {"failed", "attempted"}
FAILURE_EVENT_TYPES = {"payment_failed", "otp_failed"}
ABANDON_EVENT_TYPES = {"checkout_abandoned", "checkout_closed"}


def _records(db: Session, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    sessions_q = db.query(CheckoutSession).filter(
        CheckoutSession.started_at >= start, CheckoutSession.started_at < end
    )
    if merchant_id:
        sessions_q = sessions_q.filter(CheckoutSession.merchant_id == merchant_id)
    sessions = sessions_q.order_by(CheckoutSession.started_at.desc()).all()
    if not sessions:
        return []

    session_ids = [s.session_id for s in sessions]
    events_q = db.query(CheckoutEvent).filter(CheckoutEvent.session_id.in_(session_ids))
    if merchant_id:
        events_q = events_q.filter(CheckoutEvent.merchant_id == merchant_id)
    events = events_q.order_by(CheckoutEvent.created_at.asc()).all()
    events_by_session: dict[str, list[CheckoutEvent]] = defaultdict(list)
    for event in events:
        events_by_session[event.session_id].append(event)

    order_ids = {s.order_id for s in sessions if s.order_id}
    payment_rows = []
    if order_ids:
        payment_rows = (
            db.query(Payment)
            .filter((Payment.order_id.in_(order_ids)) | (Payment.rzp_order_id.in_(order_ids)))
            .all()
        )
    payments_by_order: dict[str, Payment] = {}
    for payment in payment_rows:
        if payment.order_id:
            payments_by_order[payment.order_id] = payment
        if payment.rzp_order_id:
            payments_by_order[payment.rzp_order_id] = payment

    records = []
    for session in sessions:
        session_events = events_by_session.get(session.session_id, [])
        payment = payments_by_order.get(session.order_id)
        event_types = {event.event_type for event in session_events}
        completed = session.status == "completed" or "payment_completed" in event_types
        if payment and payment.status in SUCCESS_PAYMENT_STATUSES:
            completed = True
        failed = not completed and (
            bool(event_types & FAILURE_EVENT_TYPES)
            or bool(payment and payment.status in FAILED_PAYMENT_STATUSES)
        )
        abandoned = not completed and bool(event_types & ABANDON_EVENT_TYPES)
        checkout_status = "completed" if completed else "failed" if failed else "abandoned" if abandoned else session.status
        failure_reason = _reason(session_events, payment, failed, abandoned)
        customer = _customer(session_events, payment)
        amount = to_float(payment.amount) if payment else _event_amount(session_events)
        records.append({
            "session_id": session.session_id,
            "checkout_id": session.session_id,
            "customer": {
                "name": customer["name"],
                "email": customer["email"],
                "contact": customer["contact"],
            },
            "customer_name": customer["name"],
            "amount": amount,
            "payment_id": payment.payment_id if payment else session.payment_id,
            "payment_status": payment.status if payment else ("captured" if completed else None),
            "checkout_status": checkout_status,
            "failure_reason": failure_reason,
            "created_at": iso(session.started_at),
            "updated_at": iso(session.updated_at),
            "completed": completed,
            "failed": failed,
            "dropped_off": abandoned,
        })
    return records


def _event_amount(events: list[CheckoutEvent]) -> float | None:
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        amount = to_float(payload.get("amount"))
        if amount is not None:
            return amount
    return None


def _customer(events: list[CheckoutEvent], payment: Payment | None) -> dict:
    if payment:
        return {"name": payment.customer_name, "email": payment.email, "contact": payment.contact}
    for event in reversed(events):
        payload = event.payload if isinstance(event.payload, dict) else {}
        customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
        name = customer.get("name") or payload.get("customer_name") or payload.get("name")
        email = customer.get("email") or payload.get("email")
        contact = customer.get("contact") or payload.get("contact")
        if name or email or contact:
            return {"name": name, "email": email, "contact": contact}
    return {"name": None, "email": None, "contact": None}


def _reason(events: list[CheckoutEvent], payment: Payment | None, failed: bool, abandoned: bool) -> str | None:
    for event in reversed(events):
        if event.error_reason:
            return event.error_reason
        payload = event.payload if isinstance(event.payload, dict) else {}
        reason = payload.get("error_reason") or payload.get("failure_reason") or payload.get("reason")
        if reason:
            return str(reason)
    if payment and payment.failure_reason:
        return payment.failure_reason
    if failed:
        return "Payment failed"
    if abandoned:
        return "Checkout abandoned"
    return None


def summary(db: Session, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> dict:
    records = _records(db, from_date, to_date, merchant_id=merchant_id)
    attempts = len(records)
    completed = sum(r["completed"] for r in records)
    failed = sum(r["failed"] for r in records)
    dropped = sum(r["dropped_off"] for r in records)
    return {
        "total_checkout_attempts": attempts,
        "completed_checkouts": completed,
        "dropped_off_checkouts": dropped,
        "conversion_rate": round(completed / attempts * 100, 1) if attempts else 0,
        "failed_checkouts": failed,
    }


def trend(db: Session, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    by_date: dict[str, dict] = {}
    for record in _records(db, from_date, to_date, merchant_id=merchant_id):
        day = str(record["created_at"])[:10]
        bucket = by_date.setdefault(day, {"date": day, "attempts": 0, "completed": 0, "dropped_off": 0, "failed": 0})
        bucket["attempts"] += 1
        bucket["completed"] += int(record["completed"])
        bucket["dropped_off"] += int(record["dropped_off"])
        bucket["failed"] += int(record["failed"])
    return [by_date.get(day.isoformat(), {"date": day.isoformat(), "attempts": 0, "completed": 0, "dropped_off": 0, "failed": 0}) for day in calendar_days(start, end)]


def dropoff_reasons(db: Session, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> list[dict]:
    records = _records(db, from_date, to_date, merchant_id=merchant_id)
    reasons: dict[str, int] = defaultdict(int)
    for record in records:
        if record["failed"] or record["dropped_off"]:
            reasons[record["failure_reason"] or "Unknown"] += 1
    total = sum(reasons.values())
    return [
        {"reason": reason, "count": count, "percentage": round(count / total * 100, 1) if total else 0}
        for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
    ]


def recent(db: Session, from_date: str | None, to_date: str | None, limit: int = 20, merchant_id: str | None = None) -> list[dict]:
    return _records(db, from_date, to_date, merchant_id=merchant_id)[:limit]
