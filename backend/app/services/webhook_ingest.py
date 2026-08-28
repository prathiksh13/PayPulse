from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    MandateEvent,
    Payment,
    PaymentAttempt,
    PaymentEvent,
    UpiMandate,
)
from ..utils.helpers import now_utc, to_float
from .serializers import payment_status_from_rzp


class WebhookError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _event_id(payload: dict) -> str:
    event = payload.get("event") or "unknown"
    created = payload.get("created_at") or 0
    entity_parts = []

    def dig(obj, keys):
        for k in keys:
            if isinstance(obj, dict) and obj.get(k):
                entity_parts.append(str(obj[k]))

    dig(payload, ["id"])
    p_payload = payload.get("payload") or {}
    for key in ("payment", "order", "mandate", "payment_link", "refund", "customer", "subscription"):
        entity = (p_payload.get(key) or {}).get("entity") or {}
        dig(entity, ["id"])
    return f"{event}:{created}:{':'.join(entity_parts) or 'noid'}"


def process_webhook(db: Session, payload: dict, raw_body: bytes | None = None) -> dict:
    """Store a validated Razorpay webhook event exactly once and update state."""
    if not isinstance(payload, dict) or not payload.get("event"):
        raise WebhookError("Malformed webhook payload: missing event field.")

    event = payload.get("event", "")
    event_id = _event_id(payload)

    # Duplicate prevention: the event_id column is unique.
    existing = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    if existing:
        return {"status": "duplicate", "event_id": event_id, "processing": False}

    db.add(PaymentEvent(
        event_id=event_id,
        payment_id=_payload_payment_id(payload) or "unknown",
        event_type=event,
        status=None,
        error_code=None,
        error_reason=None,
        payload=payload,
        received_at=now_utc(),
    ))

    if event.startswith("payment."):
        _handle_payment_event(db, event, payload)
    elif event.startswith("mandate."):
        _handle_mandate_event(db, event, payload)
    elif event.startswith("order."):
        _handle_order_event(db, payload)
    elif event.startswith("payment_link."):
        _handle_payment_link_event(db, payload)
    elif event.startswith("refund."):
        _handle_refund_event(db, payload)
    else:
        # events we don't transform yet are still stored for the event stream
        pass

    db.commit()
    return {"status": "processed", "event_id": event_id, "event": event, "processing": True}


def store_payment_from_api(db: Session, payment_entity: dict, event_type: str = "payment.captured") -> bool:
    """Persist a payment pulled directly from the Razorpay API (checkout flow).

    Reuses the webhook storage path so both sources write identically, and the
    same event deduping applies (unique event_id = event : created_at : entity id).
    Returns True if stored, False if it was already seen (duplicate)."""
    if not isinstance(payment_entity, dict) or not payment_entity.get("id"):
        raise WebhookError("Payment entity missing id")

    now = now_utc()
    event_type = event_type if event_type.startswith("payment.") else f"payment.{event_type}"
    payload = {
        "event": event_type,
        "created_at": payment_entity.get("created_at") or int(now.timestamp()),
        "payload": {"payment": {"entity": payment_entity}},
    }
    event_id = _event_id(payload)
    existing = db.query(PaymentEvent).filter(PaymentEvent.event_id == event_id).first()
    if existing:
        return False

    db.add(PaymentEvent(
        event_id=event_id,
        payment_id=payment_entity.get("id"),
        event_type=event_type,
        status=payment_entity.get("status"),
        error_code=payment_entity.get("error_code"),
        error_reason=payment_entity.get("error_description"),
        payload=payload,
        received_at=now,
    ))
    _handle_payment_event(db, event_type, payload)
    db.commit()
    return True


def _raw_entity(payload: dict, key: str) -> dict:
    p_payload = payload.get("payload") or {}
    entity = (p_payload.get(key) or {}).get("entity")
    return entity if isinstance(entity, dict) else {}


def _payload_payment_id(payload: dict) -> str | None:
    return _raw_entity(payload, "payment").get("id")


def _handle_payment_event(db: Session, event: str, payload: dict):
    entity = _raw_entity(payload, "payment")
    if not entity:
        return
    pid = entity.get("id")
    if not pid:
        return

    amount_inr = to_float(entity.get("amount"))
    if amount_inr is not None:
        amount_inr = round(amount_inr / 100, 2)  # paise -> rupees
    status = payment_status_from_rzp(entity.get("status"))
    method = entity.get("method")
    order_id = entity.get("order_id")
    error_code = entity.get("error_code")
    error_reason = entity.get("error_description")
    description = entity.get("description")
    email = entity.get("email")
    contact = entity.get("contact")
    notes = entity.get("notes") or {}
    customer_name = ""
    if isinstance(notes, dict):
        customer_name = notes.get("customer_name") or notes.get("name") or ""

    rzp_mandate_id = None
    if isinstance(notes, dict):
        rzp_mandate_id = notes.get("mandate_id") or notes.get("rzp_mandate_id")

    payment = db.query(Payment).filter(Payment.payment_id == pid).first()
    if payment is None:
        payment = Payment(
            payment_id=pid,
            order_id=order_id,
            rzp_order_id=order_id,
            rzp_mandate_id=rzp_mandate_id,
            amount=amount_inr,
            currency=entity.get("currency") or "INR",
            method=method,
            status=status,
            failure_code=error_code,
            failure_reason=error_reason,
            email=email,
            contact=contact,
            customer_name=customer_name,
            description=description,
            raw=entity,
        )
        db.add(payment)
        db.flush()
    else:
        payment.amount = amount_inr if amount_inr is not None else payment.amount
        payment.order_id = order_id or payment.order_id
        payment.rzp_order_id = order_id or payment.rzp_order_id
        payment.method = method or payment.method
        payment.status = status
        if error_code:
            payment.failure_code = error_code
        if error_reason:
            payment.failure_reason = error_reason
        if email:
            payment.email = email
        if contact:
            payment.contact = contact
        if customer_name:
            payment.customer_name = customer_name
        if rzp_mandate_id:
            payment.rzp_mandate_id = rzp_mandate_id
        if entity.get("order_id"):
            payment.rzp_order_id = entity.get("order_id")

    # capture details when present
    if isinstance(entity.get("fee"), (int, float)) or entity.get("fee") is not None:
        pass  # fee/tax not stored on model — kept in raw

    # attempt tracking
    attempt_id = entity.get("id") or pid
    attempt = db.query(PaymentAttempt).filter(PaymentAttempt.attempt_id == attempt_id).first()
    if attempt is None:
        db.add(PaymentAttempt(
            attempt_id=attempt_id,
            payment_id=pid,
            txn_id=entity.get("acquirer_data", {}).get("transaction_id") if isinstance(entity.get("acquirer_data"), dict) else None,
            status=entity.get("status"),
            amount=amount_inr,
            method=method,
            error_code=error_code,
            error_reason=error_reason,
        ))
        payment.attempt_count = (payment.attempt_count or 0) + 1
    else:
        attempt.status = entity.get("status")
        attempt.error_code = error_code
        attempt.error_reason = error_reason


def _handle_mandate_event(db: Session, event: str, payload: dict):
    entity = _raw_entity(payload, "mandate")
    if not entity:
        return
    mid = entity.get("id")
    if not mid:
        return

    m = db.query(UpiMandate).filter(UpiMandate.mandate_id == mid).first()
    if m is None:
        notes = entity.get("notes") or {}
        m = UpiMandate(
            mandate_id=mid,
            rzp_order_id=entity.get("order_id"),
            customer_id=entity.get("customer_id"),
            customer_name=notes.get("customer_name") if isinstance(notes, dict) else None,
            customer_email=notes.get("email") if isinstance(notes, dict) else None,
            customer_contact=notes.get("contact") if isinstance(notes, dict) else None,
            frequency=entity.get("frequency"),
            status="pending",
            raw=entity,
        )
        db.add(m)
        db.flush()

    status_map = {
        "mandate.activated": "active",
        "mandate.created": "pending",
        "mandate.authorized": "active",
        "mandate.started": "processing",
        "mandate.halted": "failed",
        "mandate.failed": "failed",
        "mandate.rejected": "failed",
        "mandate.cancelled": "cancelled",
        "mandate.expired": "expired",
        "mandate.paused": "paused",
    }
    status = status_map.get(event, m.status)
    error_reason = None
    if status in ("failed", "rejected"):
        error_reason = (
            entity.get("status_details", {}).get("error_description")
            if isinstance(entity.get("status_details"), dict)
            else entity.get("error_description")
        )
    m.status = status
    if error_reason:
        m.failure_reason = error_reason
    if not m.failure_reason and "failure" in event:
        m.failure_reason = (entity.get("error_description") or entity.get("error_reason")) or "Mandate activation failed"

    # next debit date
    fpd = entity.get("first_payment_date") or entity.get("next_debit_date")
    if fpd:
        try:
            m.next_debit_at = datetime.fromtimestamp(int(fpd), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass

    db.add(MandateEvent(
        event_id=_event_id(payload),
        mandate_id=mid,
        event_type=event,
        status=status,
        error_code=entity.get("error_code"),
        error_reason=error_reason,
        payload=payload,
        received_at=now_utc(),
    ))


def _handle_order_event(db: Session, payload: dict):
    entity = _raw_entity(payload, "order")
    if not entity:
        return
    oid = entity.get("id")
    status = entity.get("status")
    amount_inr = to_float(entity.get("amount"))
    if amount_inr is not None:
        amount_inr = round(amount_inr / 100, 2)

    placeholder_id = f"order-{oid}"
    payment = db.query(Payment).filter(Payment.payment_id == placeholder_id).first()
    if status == "paid" and amount_inr:
        # If a real payment webhook told us about this order already, leave it alone.
        real = db.query(Payment).filter(Payment.rzp_order_id == oid).first()
        if real is not None:
            return
        if payment is None:
            db.add(Payment(
                payment_id=placeholder_id,
                order_id=oid,
                rzp_order_id=oid,
                amount=amount_inr,
                currency=entity.get("currency") or "INR",
                status="pending",
                raw=entity,
            ))


def _handle_payment_link_event(db: Session, payload: dict):
    entity = _raw_entity(payload, "payment_link")
    if not entity:
        return
    pid = entity.get("id")
    order_id = entity.get("order_id")
    status = entity.get("status")  # paid | cancelled
    amount_inr = to_float(entity.get("amount"))
    if amount_inr is not None:
        amount_inr = round(amount_inr / 100, 2)

    payments = db.query(Payment).filter(Payment.order_id == order_id, Payment.status == "pending").all()
    if not payments:
        return
    for p in payments:
        p.link_id = pid
        if status == "paid":
            p.status = "captured"
        elif status == "cancelled":
            p.status = "cancelled"


def _handle_refund_event(db: Session, payload: dict):
    entity = _raw_entity(payload, "refund")
    if not entity:
        return
    pid = entity.get("payment_id")
    if not pid:
        return
    payment = db.query(Payment).filter(Payment.payment_id == pid).first()
    if payment is None:
        return
    refund_amount = to_float(entity.get("amount"))
    if refund_amount is not None:
        refund_amount = round(refund_amount / 100, 2)
        payment.refunded_amount = (to_float(payment.refunded_amount) or 0) + refund_amount
        if payment.refunded_amount >= (to_float(payment.amount) or 0):
            payment.status = "refunded"
            payment.is_refunded = True
        else:
            payment.status = "partially_refunded"