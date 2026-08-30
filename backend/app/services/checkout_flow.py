# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Payment
from ..utils.helpers import to_float
from ..utils.security import verify_checkout_signature
from .checkout_service import CheckoutError
from .razorpay_client import RazorpayClient, RazorpayError
from .serializers import payment_to_dict
from .webhook_ingest import store_payment_from_api

MAX_ORDER_AMOUNT = 200_000  # ₹ test ceiling


def create_order(
    db: Session,
    amount: float | int | str | None,
    currency: str = "INR",
    receipt: str | None = None,
) -> dict:
    """Create a Razorpay Order (Test Mode). Returns public fields only —
    the key secret never leaves the backend."""
    try:
        amount_inr = to_float(amount)
    except (TypeError, ValueError):
        amount_inr = None
    if not amount_inr or amount_inr <= 0:
        raise CheckoutError("amount must be a positive number in INR", 400)
    if amount_inr > MAX_ORDER_AMOUNT:
        raise CheckoutError(f"Test payments are capped at ₹{'%g' % MAX_ORDER_AMOUNT}", 400)
    currency = (currency or "INR").upper()

    client = RazorpayClient()
    if not client.configured:
        raise CheckoutError(
            "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured in backend/.env", 503
        )

    try:
        order = client.create_order(amount_inr, currency, receipt or f"pulse-{uuid.uuid4().hex[:10]}")
    except RazorpayError as exc:
        raise CheckoutError(str(exc), 502) from exc

    return {
        "order_id": order["order_id"],
        "amount": to_float(order.get("amount")) / 100 if order.get("amount") else amount_inr,
        "amount_paise": int(order.get("amount") or round(amount_inr * 100)),
        "currency": order.get("currency") or currency,
        "receipt": order.get("receipt"),
        "key_id": settings.razorpay_key_id,  # public key — safe to expose
        "merchant": settings.app_name,
    }


def verify_and_store(
    db: Session,
    order_id: str,
    payment_id: str,
    signature: str | None,
) -> dict:
    """Verify the checkout signature server-side, then sync the payment to DB."""
    if not (order_id and payment_id):
        raise CheckoutError("order_id and payment_id are required", 400)

    if not verify_checkout_signature(order_id, payment_id, signature):
        raise CheckoutError("Payment signature verification failed", 400)

    client = RazorpayClient()
    if not client.configured:
        raise CheckoutError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured in backend/.env", 503)

    try:
        payment = client.get_payment(payment_id)
    except RazorpayError as exc:
        raise CheckoutError(f"Could not fetch payment from Razorpay: {exc}", 502) from exc

    if payment.get("order_id") and payment.get("order_id") != order_id:
        raise CheckoutError("Payment does not match the reported order", 400)

    status = (payment.get("status") or "").lower()
    event_type = {
        "captured": "payment.captured",
        "authorized": "payment.authorized",
        "paid": "payment.captured",
        "failed": "payment.failed",
        "attempted": "payment.failed",
    }.get(status, "payment.captured")

    stored = store_payment_from_api(db, payment, event_type)

    row = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    return {
        "ok": True,
        "stored": stored,
        "payment_id": payment_id,
        "order_id": order_id,
        "status": row.status if row else payment.get("status"),
        "payment": payment_to_dict(row) if row else None,
    }


def fetch_and_store(db: Session, payment_id: str) -> dict:
    """Sync a payment (e.g. a failed checkout from the SDK) without a signature."""
    if not payment_id:
        raise CheckoutError("payment_id is required", 400)

    client = RazorpayClient()
    if not client.configured:
        raise CheckoutError("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not configured in backend/.env", 503)

    try:
        payment = client.get_payment(payment_id)
    except RazorpayError as exc:
        raise CheckoutError(f"Could not fetch payment from Razorpay: {exc}", 502) from exc

    status = (payment.get("status") or "").lower()
    event_type = {
        "captured": "payment.captured",
        "authorized": "payment.authorized",
        "paid": "payment.captured",
        "failed": "payment.failed",
        "attempted": "payment.failed",
    }.get(status)
    if event_type is None:
        raise CheckoutError(f"Payment status '{status}' cannot be recorded yet", 400)

    stored = store_payment_from_api(db, payment, event_type)

    row = db.query(Payment).filter(Payment.payment_id == payment_id).first()
    return {
        "ok": True,
        "stored": stored,
        "payment_id": payment_id,
        "status": row.status if row else payment.get("status"),
        "payment": payment_to_dict(row) if row else None,
    }