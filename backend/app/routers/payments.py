# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Payment, PaymentAttempt, PaymentEvent, RecoveryAction
from ..services.analytics import payment_series
from ..services.razorpay_client import RazorpayClient, RazorpayError
from ..services.serializers import (
    payment_detail_to_dict,
    payment_to_dict,
)
from ..services.settings_service import recovery_policy
from ..utils.cache import clear_cache
from ..utils.helpers import iso, now_utc, resolve_range, to_float

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("")
def list_payments(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    query: str | None = None,
    status: str | None = None,
    method: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    page: int | None = Query(None, ge=1),
    limit: int | None = Query(None, ge=1, le=500),
    sort: str = "created_at",
    sort_dir: str = "desc",
    group: str | None = None,
):
    start, end = resolve_range(from_date, to_date)

    if group == "day":
        return {"items": payment_series(db, from_date, to_date, group="day"), "group": "day"}

    q = db.query(Payment).filter(Payment.created_at >= start, Payment.created_at < end)

    if status:
        q = q.filter(Payment.status == status)
    if method:
        q = q.filter(Payment.method == method)
    if min_amount is not None:
        q = q.filter(Payment.amount >= min_amount)
    if max_amount is not None:
        q = q.filter(Payment.amount <= max_amount)
    if query:
        like = f"%{query.lower()}%"
        q = q.filter(
            or_(
                Payment.payment_id.ilike(like),
                Payment.order_id.ilike(like),
                Payment.email.ilike(like),
                Payment.contact.ilike(like),
                Payment.customer_name.ilike(like),
                Payment.description.ilike(like),
            )
        )

    total = q.count()
    sort_col = {
        "created_at": Payment.created_at,
        "amount": Payment.amount,
        "status": Payment.status,
        "method": Payment.method,
        "id": Payment.payment_id,
    }.get(sort, Payment.created_at)
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    rows = q.order_by(order).offset(((page or 1) - 1) * (limit or 100)).limit(limit or 100).all()

    return {
        "items": [payment_to_dict(p) for p in rows],
        "total": total,
        "page": page or 1,
        "limit": limit or 100,
        "has_more": ((page or 1) * (limit or 100)) < total,
    }


@router.post("/{payment_id}/refund")
def refund_payment_endpoint(
    payment_id: str,
    body: dict | None = None,
    db: Session = Depends(get_db),
):
    """Refund a captured/authorized payment through Razorpay and persist the result.

    Only captured/authorized payments that have remaining un-refunded funds are
    eligible — failed-never-captured payments cannot be refunded here.
    """
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    status = payment.status or ""
    if status not in ("captured", "authorized"):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Refund is only valid for captured/authorized payments that settled "
                f"funds (current status: {status})."
            ),
        )

    settled = to_float(payment.amount) or 0
    refunded = to_float(payment.refunded_amount) or 0
    remaining = max(settled - refunded, 0)
    if remaining <= 0:
        raise HTTPException(status_code=409, detail="Payment is already fully refunded.")

    requested = None
    if isinstance(body, dict) and body.get("amount") not in (None, ""):
        requested = to_float(body.get("amount"))
        if requested <= 0:
            raise HTTPException(status_code=422, detail="Refund amount must be positive.")
        if requested > remaining:
            raise HTTPException(
                status_code=422,
                detail=f"Refund amount ₹{requested} exceeds remaining refundable ₹{remaining}.",
            )
    amount = requested or remaining

    policy = recovery_policy(db)
    if amount > policy["max_refund_amount"]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Refund blocked by safety policy: ₹{amount} exceeds limit "
                f"₹{policy['max_refund_amount']}."
            ),
        )

    try:
        client = RazorpayClient()
        refund = client.refund_payment(payment.payment_id, amount)
    except RazorpayError as exc:
        raise HTTPException(status_code=502, detail=f"Razorpay refund failed: {exc}")

    provider_ref_id = refund.get("provider_ref_id")
    payment.refunded_amount = round(refunded + amount, 2)
    fully = payment.refunded_amount >= settled
    payment.is_refunded = fully
    payment.status = "refunded" if fully else "partially_refunded"

    db.add(AuditLog(
        actor="merchant@dashboard",
        actor_type="merchant",
        action="payment.refund",
        entity_type="payment",
        entity_id=payment_id,
        detail={
            "amount": amount,
            "provider_ref_id": provider_ref_id,
            "refunded_amount": payment.refunded_amount,
            "status": payment.status,
        },
    ))
    db.commit()
    clear_cache()

    return {
        "ok": True,
        "payment": payment_to_dict(payment),
        "refund": {
            "payment_id": payment_id,
            "amount": amount,
            "provider_ref_id": provider_ref_id,
            "refunded_amount": payment.refunded_amount,
            "status": payment.status,
            "created_at": iso(now_utc()),
        },
    }


@router.get("/{payment_id}")
def get_payment_detail(payment_id: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    attempts = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.payment_id == payment_id)
        .order_by(PaymentAttempt.created_at.asc())
        .all()
    )
    events = (
        db.query(PaymentEvent)
        .filter(PaymentEvent.payment_id == payment_id)
        .order_by(PaymentEvent.received_at.asc())
        .all()
    )
    recovery = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.payment_id == payment_id)
        .order_by(RecoveryAction.created_at.desc())
        .first()
    )
    return payment_detail_to_dict(payment, attempts, events, recovery)