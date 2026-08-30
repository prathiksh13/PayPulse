from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyReport
from ..services.reports import VALID_TYPES, generate_report, persist_daily_report
from ..utils.helpers import resolve_range
from ..services.report_summary import build_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary")
def summary_report(
    period: str = Query("7d"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
):
    if period not in {"today", "7d", "30d"} and not (from_date and to_date):
        raise HTTPException(status_code=422, detail="period must be today, 7d, or 30d")
    try:
        return build_summary(db, period, from_date, to_date)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Report data is temporarily unavailable") from exc


@router.get("")
def get_report(
    report_type: str = Query("daily", alias="type"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    t = (report_type or "daily").lower()
    if t not in VALID_TYPES:
        t = "daily"
    report = generate_report(db, t, from_date, to_date)
    if t in ("daily", "payment"):
        start, end = resolve_range(from_date, to_date)
        background_tasks.add_task(
            persist_daily_report,
            dict(report["metrics"]),
            start.date(),
            (end - timedelta(days=1)).date(),
        )
    return report


@router.get("/history")
def reports_history(db: Session = Depends(get_db)):
    rows = (
        db.query(DailyReport)
        .order_by(DailyReport.report_date.desc())
        .limit(30)
        .all()
    )
    return {
        "items": [
            {
                "id": f"report-{r.report_date.isoformat()}",
                "type": r.report_type,
                "report_date": r.report_date.isoformat(),
                "period_from": r.period_from.isoformat() if r.period_from else None,
                "period_to": r.period_to.isoformat() if r.period_to else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
