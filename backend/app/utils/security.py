# -*- coding: utf-8 -*-
import hashlib
import hmac

from ..config import settings


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verify a Razorpay webhook signature (HMAC-SHA256 of the raw body using
    the webhook secret). Accepts both raw hex and ``sha256=...`` prefixed forms."""
    if not signature:
        return False
    if not settings.webhook_configured:
        return False
    if signature.startswith("sha256="):
        signature = signature.split("=", 1)[1]
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_checkout_signature(order_id: str, payment_id: str, signature: str | None) -> bool:
    """Verifies the Razorpay Checkout response signature.

    Razorpay computes ``HMAC-SHA256(order_id + "|" + payment_id, key_secret)``.
    Done server-side only — the key secret never leaves the backend."""
    if not signature or not settings.razorpay_key_secret:
        return False
    expected = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def canary_error(message: str) -> dict:
    return {"ok": False, "error": message}