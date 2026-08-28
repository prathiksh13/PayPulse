from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.notifications import build_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    items = build_notifications(db, limit)
    return {
        "items": items,
        "total": len(items),
        "unread": sum(1 for n in items if not n.get("read")),
    }