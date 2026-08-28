from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
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
):
    return compute_summary(db, from_date, to_date)


@router.get("/failure-breakdown")
def breakdown(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = 12,
    db: Session = Depends(get_db),
):
    return {"items": failure_breakdown(db, from_date, to_date, limit)}


@router.get("/methods")
def methods(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return {"items": method_distribution(db, from_date, to_date)}


@router.get("/mandates")
def mandates(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    return mandate_stats(db, from_date, to_date)


@router.get("/series")
def series(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    group: str = "day",
    db: Session = Depends(get_db),
):
    return {"items": payment_series(db, from_date, to_date, group)}