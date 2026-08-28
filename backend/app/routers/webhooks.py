from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_pipeline import analyze_failures
from ..services.checkout_service import CheckoutError, ingest_session_events
from ..services.webhook_ingest import WebhookError, process_webhook
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

    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    try:
        result = process_webhook(db, payload, raw_body)
    except WebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if result.get("processing"):
        # Fire the AI failure-analysis pipeline after the webhook is acked
        # (anomaly detection + Groq root cause + recovery recommendation).
        background_tasks.add_task(analyze_failures)
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