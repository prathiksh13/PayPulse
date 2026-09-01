from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..routers.auth import CurrentUser, get_current_user
from ..services import checkout_intelligence

router = APIRouter(prefix="/checkout-intelligence", tags=["checkout-intelligence"])


@router.get("/summary")
def checkout_summary(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return checkout_intelligence.summary(db, from_date, to_date, merchant_id=current_user.merchant_id)


@router.get("/trend")
def checkout_trend(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": checkout_intelligence.trend(db, from_date, to_date, merchant_id=current_user.merchant_id)}


@router.get("/dropoff-reasons")
def checkout_dropoff_reasons(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": checkout_intelligence.dropoff_reasons(db, from_date, to_date, merchant_id=current_user.merchant_id)}


@router.get("/recent")
def recent_checkouts(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": checkout_intelligence.recent(db, from_date, to_date, limit, merchant_id=current_user.merchant_id)}
