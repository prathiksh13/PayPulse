from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DailyReport
from ..services.reports import VALID_TYPES, generate_report, persist_daily_report
from ..utils.helpers import resolve_range

router = APIRouter(prefix="/reports", tags=["reports"])


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