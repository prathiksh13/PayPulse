from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    Anomaly,
    DailyReport,
    Payment,
)
from ..utils.helpers import iso, resolve_range, to_float
from . import analytics as analytics_svc
from .recovery_engine import recovered_amount, recovery_history

VALID_TYPES = ("daily", "failure", "recovery", "upi", "checkout", "ai_operations")


def _base_metrics(db: Session, from_date: str | None, to_date: str | None) -> dict:
    s = analytics_svc.compute_summary(db, from_date, to_date)
    breakdown = analytics_svc.failure_breakdown(db, from_date, to_date, limit=8)
    recovered = recovered_amount(db)
    failed = s.get("failed") or 0
    recovery_rate = (recovered / (recovered + (s.get("amount_at_risk") or 0)) * 100) if recovered else None

    return {
        "payment_volume": s.get("volume"),
        "transactions": s.get("transactions"),
        "success_rate": s.get("success_rate"),
        "failure_rate": round(100 - s.get("success_rate"), 1) if s.get("success_rate") is not None else None,
        "failed": failed,
        "amount_lost": s.get("amount_at_risk"),
        "amount_recovered": recovered,
        "recovery_rate": round(recovery_rate, 1) if recovery_rate is not None else None,
        "amount_at_risk": s.get("amount_at_risk"),
        "checkout_abandonment": s.get("checkout_abandonment"),
        "top_failure_causes": breakdown,
    }


def generate_report(db: Session, report_type: str, from_date: str | None, to_date: str | None) -> dict:
    """Pure DB-computation of a report. Never touches the LLM. The dailies
    snapshot is persisted separately via persistence so this stays fast."""
    report_type = (report_type or "daily").lower()
    if report_type not in VALID_TYPES:
        report_type = "daily"
    start, end = resolve_range(from_date, to_date)
    metrics = _base_metrics(db, from_date, to_date)

    if report_type == "failure":
        extra["failure_breakdown"] = analytics_svc.failure_breakdown(db, from_date, to_date, limit=10)
        extra["by_code"] = analytics_svc.failure_code_breakdown(db, from_date, to_date, limit=10)
        extra["by_method"] = analytics_svc.method_distribution(db, from_date, to_date)

    if report_type == "recovery":
        extra["history"] = recovery_history(db, from_date, to_date, limit=50)
        extra["recovered_amount"] = metrics["amount_recovered"]
        extra["outstanding"] = (
            db.query(Payment)
            .filter(Payment.status.in_(("failed", "attempted")))
            .count()
        )

    if report_type == "upi":
        extra["mandates"] = analytics_svc.mandate_stats(db, from_date, to_date)
        extra["upi_failures"] = (
            db.query(Payment)
            .filter(Payment.method == "upi", Payment.status.in_(("failed", "attempted")))
            .count()
        )

    if report_type == "checkout":
        extra["checkout"] = analytics_svc.checkout_analytics(db, from_date, to_date)

    if report_type == "ai_operations":
        active = db.query(Anomaly).filter(Anomaly.status == "active").count()
        resolved = db.query(Anomaly).filter(Anomaly.status == "resolved").count()
        extra["anomalies"] = {"active": active, "resolved": resolved}
        extra["agent"] = {
            "actions_executed": db.query(Payment).count(),
            "recovered_revenue": metrics["amount_recovered"],
        }

    report = {
        "id": f"report-{report_type}-{start.date().isoformat()}",
        "type": report_type,
        "period": {"from": iso(start), "to": iso(end)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metrics": dict(metrics),
        **metrics,
        **extra,
    }
    return report


def persist_daily_report(metrics: dict, period_from, period_to) -> None:
    """Background persistence of the daily snapshot (upsert). Runs in its own
    session so it never blocks the request that generated the report."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        day = date.today()
        existing = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == day, DailyReport.report_type == "daily")
            .first()
        )
        if existing:
            existing.metrics = metrics
        else:
            db.add(DailyReport(
                report_date=day,
                report_type="daily",
                period_from=period_from,
                period_to=period_to,
                metrics=metrics,
            ))
        db.commit()
    finally:
        db.close()