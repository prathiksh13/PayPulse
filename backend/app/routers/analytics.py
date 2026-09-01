from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..routers.auth import CurrentUser, get_current_user
from ..services.analytics import (
    compute_summary,
    failure_breakdown,
    mandate_stats,
    method_distribution,
    payment_series,
)

router = APIRouter(prefix="/dashboard", tags=["analytics"])


@router.get("/summary")
def dashboard_summary(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return compute_summary(db, from_date, to_date, merchant_id=current_user.merchant_id)


@router.get("/failure-breakdown")
def breakdown(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = 12,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": failure_breakdown(db, from_date, to_date, limit, merchant_id=current_user.merchant_id)}


@router.get("/methods")
def methods(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": method_distribution(db, from_date, to_date, merchant_id=current_user.merchant_id)}


@router.get("/mandates")
def mandates(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return mandate_stats(db, from_date, to_date, merchant_id=current_user.merchant_id)


@router.get("/series")
def series(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    group: str = "day",
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return {"items": payment_series(db, from_date, to_date, group, merchant_id=current_user.merchant_id)}