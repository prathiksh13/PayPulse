from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"
    return {
        "status": "ok",
        "service": "payment-operations-agent",
        "version": settings.app_version,
        "database": db_status,
        "razorpay_configured": settings.razorpay_configured,
        "groq_configured": settings.groq_configured,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }