from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import checkout_flow
from ..services.ai_pipeline import analyze_failures
from ..services.analytics import checkout_analytics
from ..services.checkout_service import ingest_session_events
from ..services.checkout_service import CheckoutError, record_order_started

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.get("/analytics")
def get_checkout_analytics(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return checkout_analytics(db, from_date, to_date)


@router.post("/events")
async def post_checkout_events(body: dict, db: Session = Depends(get_db)):
    """Alias of POST /api/webhooks/checkout for merchant SDK ingestion."""
    events = body.get("events") if isinstance(body, dict) else None
    if events is None:
        events = [body]
    if not isinstance(events, list) or len(events) == 0:
        raise HTTPException(status_code=400, detail="No events provided")
    try:
        result = ingest_session_events(db, events)
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {"ok": True, **result}


@router.post("/order")
def create_test_order(body: dict, db: Session = Depends(get_db)):
    """Create a Razorpay Order (Test Mode) for the Checkout SDK.
    Returns the public key_id only — never the key secret."""
    try:
        result = checkout_flow.create_order(
            db,
            body.get("amount"),
            body.get("currency") or "INR",
            body.get("receipt"),
        )
        order_id = result.get("order_id")
        if order_id:
            record_order_started(db, order_id)
        return result
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("/verify")
def verify_test_payment(
    body: dict,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Verify the Checkout signature server-side and persist the payment."""
    try:
        result = checkout_flow.verify_and_store(
            db,
            body.get("razorpay_order_id") or body.get("order_id"),
            body.get("razorpay_payment_id") or body.get("payment_id"),
            body.get("razorpay_signature") or body.get("signature"),
        )
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if background_tasks:
        background_tasks.add_task(analyze_failures)
    return result


@router.post("/payment")
def sync_test_payment(
    body: dict,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Sync a payment from the SDK (e.g. a failed checkout) without a signature."""
    try:
        result = checkout_flow.fetch_and_store(db, body.get("payment_id"))
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if background_tasks:
        background_tasks.add_task(analyze_failures)
    return result