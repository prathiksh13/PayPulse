# -*- coding: utf-8 -*-
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_pipeline import analyze_failures
from ..services.checkout_service import CheckoutError, ingest_session_events
from ..services.webhook_ingest import WebhookError, process_webhook
from ..utils.plog import plog
from ..utils.security import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Razorpay webhook (signature verified, duplicate-proof). Configure this URL in
    the Razorpay Dashboard → Settings → Webhooks (Test Mode)."""
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature") or request.headers.get("x-razorpay-signature")
    event_hint = ""
    try:
        body = await request.json()
        event_hint = body.get("event", "") if isinstance(body, dict) else ""
    except Exception:  # noqa: BLE001
        body = None
    plog(f"WEBHOOK_RECEIVED event={event_hint or 'unknown'} path=/api/webhooks/razorpay bytes={len(raw_body)}")
    if isinstance(body, dict):
        entity = ((body.get("payload") or {}).get("payment") or {}).get("entity") or {}
        if entity:
            plog(
                f"PAYMENT_EVENT_RECEIVED payment_id={entity.get('id') or 'unknown'} "
                f"event={event_hint or 'unknown'} status={entity.get('status') or 'unknown'} "
                f"amount_paise={entity.get('amount') or 'unknown'} "
                f"timestamp={entity.get('created_at') or body.get('created_at') or 'unknown'}"
            )

    if not verify_webhook_signature(raw_body, signature):
        plog(f"WEBHOOK_REJECTED signature_invalid event={event_hint or 'unknown'}", level="warning")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if body is None:
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    try:
        result = process_webhook(db, body, raw_body)
    except WebhookError as exc:
        plog(f"WEBHOOK_ERROR event={event_hint or 'unknown'} detail={exc}", level="error")
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        plog(f"WEBHOOK_ERROR unhandled event={event_hint or 'unknown'} error={exc!r}", level="error")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
    if result.get("processing"):
        plog(f"WEBHOOK_PROCESSED event={result.get('event')} event_id={result.get('event_id')}")
        # Fire the AI failure-analysis pipeline after the webhook is acked
        # (anomaly detection + Groq root cause + recovery recommendation).
        background_tasks.add_task(analyze_failures)
    else:
        plog(f"WEBHOOK_DUPLICATE event_id={result.get('event_id')} status={result.get('status')}")
    return {"ok": True, **result}


@router.post("/checkout")
async def checkout_webhook(request: Request, db: Session = Depends(get_db)):
    """Ingest checkout session telemetry (checkout_started, otp_*, payment_completed,
    checkout_abandoned, payment_retry…). Accepts a single event or a batch:
    {"events": [...]}."""
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    events = body.get("events")
    if events is None:
        events = [body]

    if not isinstance(events, list) or len(events) == 0:
        raise HTTPException(status_code=400, detail="No events provided")

    try:
        result = ingest_session_events(db, events)
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"ok": True, **result}