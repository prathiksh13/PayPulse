from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    AiDecision,
    Anomaly,
    DailyReport,
    Payment,
    RecoveryAction,
)
from ..utils.helpers import iso, now_utc, resolve_range, to_float
from . import analytics as analytics_svc
from .recovery_engine import recovered_amount, recovery_history

VALID_TYPES = ("daily", "failure", "recovery", "upi", "checkout", "ai_operations")


def _query_count(db: Session, model, predicate, merchant_id: str | None = None) -> int:
    q = db.query(model).filter(predicate)
    if merchant_id:
        q = q.filter(model.merchant_id == merchant_id)
    return q.count()


def _base_metrics(db: Session, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> dict:
    s = analytics_svc.compute_summary(db, from_date, to_date, merchant_id=merchant_id)
    # bypass ttl_cache: pass merchant_id
    breakdown = analytics_svc.failure_breakdown(db, from_date, to_date, limit=8, merchant_id=merchant_id)
    recovered = recovered_amount(db, merchant_id=merchant_id)
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


def generate_report(db: Session, report_type: str, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> dict:
    """Pure DB-computation of a report. Never touches the LLM. The dailies
    snapshot is persisted separately via persistence so this stays fast."""
    report_type = (report_type or "daily").lower()
    if report_type not in VALID_TYPES:
        report_type = "daily"
    start, end = resolve_range(from_date, to_date)
    metrics = _base_metrics(db, from_date, to_date, merchant_id=merchant_id)
    extra: dict = {}

    if report_type == "failure":
        extra["failure_breakdown"] = analytics_svc.failure_breakdown(db, from_date, to_date, limit=10, merchant_id=merchant_id)
        extra["by_code"] = analytics_svc.failure_code_breakdown(db, from_date, to_date, limit=10, merchant_id=merchant_id)
        extra["by_method"] = analytics_svc.method_distribution(db, from_date, to_date, merchant_id=merchant_id)
        extra["failure_count"] = metrics.get("failed") or 0
        extra["failure_total_amount"] = metrics.get("amount_at_risk") or 0

    if report_type == "recovery":
        extra["history"] = recovery_history(db, from_date, to_date, limit=50, merchant_id=merchant_id)
        extra["recovered_amount"] = metrics["amount_recovered"]
        extra["pending_actions"] = _query_count(db, RecoveryAction, RecoveryAction.status.in_(("pending", "in_progress")), merchant_id)
        extra["executed_actions"] = _query_count(db, RecoveryAction, RecoveryAction.status == "executed", merchant_id)
        extra["outstanding"] = _query_count(db, Payment, Payment.status.in_(("failed", "attempted")), merchant_id)

    if report_type == "upi":
        extra["mandates"] = analytics_svc.mandate_stats(db, from_date, to_date, merchant_id=merchant_id)
        extra["upi_failures"] = _query_count(
            db, Payment,
            (Payment.method == "upi") & (Payment.status.in_(("failed", "attempted"))),
            merchant_id,
        )

    if report_type == "checkout":
        extra["checkout"] = analytics_svc.checkout_analytics(db, from_date, to_date, merchant_id=merchant_id)

    if report_type == "ai_operations":
        supported = Anomaly.anomaly_type.in_(analytics_svc.SUPPORTED_ANOMALY_TYPES)
        active_q = db.query(Anomaly).filter(supported, Anomaly.status == "active")
        resolved_q = db.query(Anomaly).filter(supported, Anomaly.status == "resolved")
        investigations_q = db.query(AiDecision)
        pending_q = db.query(RecoveryAction).filter(RecoveryAction.status.in_(("pending", "in_progress")))
        executed_q = db.query(RecoveryAction).filter(RecoveryAction.status == "executed")
        if merchant_id:
            active_q = active_q.filter(Anomaly.merchant_id == merchant_id)
            resolved_q = resolved_q.filter(Anomaly.merchant_id == merchant_id)
            investigations_q = investigations_q.filter(AiDecision.merchant_id == merchant_id)
            pending_q = pending_q.filter(RecoveryAction.merchant_id == merchant_id)
            executed_q = executed_q.filter(RecoveryAction.merchant_id == merchant_id)
        active = active_q.count()
        resolved = resolved_q.count()
        investigations = investigations_q.count()
        pending = pending_q.count()
        executed = executed_q.count()
        extra["anomalies"] = {"active": active, "resolved": resolved, "total": active + resolved}
        extra["investigations"] = investigations
        extra["recommendations"] = pending
        extra["executed_actions"] = executed
        extra["recovered_revenue"] = metrics["amount_recovered"]
        extra["agent"] = {
            "active_anomalies": active,
            "resolved_anomalies": resolved,
            "investigations": investigations,
            "pending_actions": pending,
            "actions_executed": executed,
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


def persist_daily_report(metrics: dict, period_from, period_to, merchant_id: str | None = None) -> None:
    """Background persistence of the daily snapshot (upsert). Runs in its own
    session so it never blocks the request that generated the report."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        day = now_utc().date()
        existing = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == day, DailyReport.report_type == "daily", DailyReport.merchant_id == merchant_id)
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
                merchant_id=merchant_id,
            ))
        db.commit()
    finally:
        db.close()
