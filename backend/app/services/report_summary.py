from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Anomaly, CheckoutEvent, Payment, RecoveryAction
from ..utils.helpers import iso, to_float
from . import checkout_intelligence

SUCCESS = {"success", "captured", "authorized"}
FAILED = {"failed", "attempted"}
ANOMALY_TYPES = {"payment_failure_spike", "payment_success_rate_drop", "payment_method_anomaly", "checkout_dropoff_spike", "repeated_failure_pattern"}


def period_range(period: str, from_date: str | None = None, to_date: str | None = None) -> tuple[datetime, datetime, int]:
    if from_date and to_date:
        start_day = date.fromisoformat(from_date[:10])
        end_day = date.fromisoformat(to_date[:10])
        days = max((end_day - start_day).days + 1, 1)
        return (
            datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
            datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
            days,
        )
    days = {"today": 1, "1d": 1, "7d": 7, "30d": 30}.get((period or "7d").lower(), 7)
    today = date.today()
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return start, end, days


def _payment_metrics(rows: list[Payment]) -> dict:
    successful = sum(1 for row in rows if row.status in SUCCESS)
    failed = sum(1 for row in rows if row.status in FAILED)
    observed = successful + failed
    volume = sum(to_float(row.amount) or 0 for row in rows)
    return {
        "total_payments": len(rows),
        "successful_payments": successful,
        "failed_payments": failed,
        "payment_volume": round(volume, 2),
        "success_rate": round(successful / observed * 100, 2) if observed else None,
        "failure_rate": round(failed / observed * 100, 2) if observed else None,
    }


def _checkout_metrics(records: list[dict]) -> dict:
    attempts = len(records)
    completed = sum(1 for record in records if record["completed"])
    abandoned = sum(1 for record in records if record["dropped_off"])
    failed = sum(1 for record in records if record["failed"])
    return {
        "checkout_attempts": attempts,
        "completed_checkouts": completed,
        "failed_checkouts": failed,
        "checkout_dropoffs": abandoned,
        "conversion_rate": round(completed / attempts * 100, 2) if attempts else None,
        "dropoff_rate": round(abandoned / attempts * 100, 2) if attempts else None,
    }


def _comparison(current: dict, previous: dict, key: str) -> dict:
    value = current.get(key)
    baseline = previous.get(key)
    if value is None or baseline in (None, 0) or not previous.get("has_data"):
        return {"current": value, "previous": baseline, "change_percent": None, "label": "Insufficient historical data"}
    return {"current": value, "previous": baseline, "change_percent": round((value - baseline) / abs(baseline) * 100, 2), "label": None}


def _failure_reasons(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.query(Payment.failure_reason, func.count(Payment.id)).filter(
        Payment.status.in_(tuple(FAILED)), Payment.created_at >= start, Payment.created_at < end,
    ).group_by(Payment.failure_reason).order_by(func.count(Payment.id).desc()).limit(10).all()
    return [{"name": reason or "Unknown", "reason": reason or "Unknown", "count": count} for reason, count in rows]


def _method_performance(db: Session, start: datetime, end: datetime) -> list[dict]:
    rows = db.query(Payment.method, Payment.status, func.count(Payment.id)).filter(
        Payment.created_at >= start, Payment.created_at < end, Payment.method.isnot(None),
    ).group_by(Payment.method, Payment.status).all()
    methods = defaultdict(lambda: {"total": 0, "failed": 0})
    for method, status, count in rows:
        if status in SUCCESS or status in FAILED:
            methods[method]["total"] += count
        if status in FAILED:
            methods[method]["failed"] += count
    return [{"method": method, "total": values["total"], "failed": values["failed"], "failure_rate": round(values["failed"] / values["total"] * 100, 2) if values["total"] else None} for method, values in sorted(methods.items())]


def _payment_trend(rows: list[Payment]) -> list[dict]:
    buckets = defaultdict(lambda: {"date": "", "successful": 0, "failed": 0, "volume": 0.0})
    for row in rows:
        key = row.created_at.date().isoformat()
        bucket = buckets[key]
        bucket["date"] = key
        bucket["successful"] += int(row.status in SUCCESS)
        bucket["failed"] += int(row.status in FAILED)
        bucket["volume"] += to_float(row.amount) or 0
    return [{**buckets[key], "volume": round(buckets[key]["volume"], 2)} for key in sorted(buckets)]


def _checkout_trend(records: list[dict]) -> list[dict]:
    buckets = defaultdict(lambda: {"date": "", "attempts": 0, "completed": 0, "dropped_off": 0})
    for record in records:
        key = str(record["created_at"])[:10]
        bucket = buckets[key]
        bucket["date"] = key
        bucket["attempts"] += 1
        bucket["completed"] += int(record["completed"])
        bucket["dropped_off"] += int(record["dropped_off"])
    return [buckets[key] for key in sorted(buckets)]


def build_summary(db: Session, period: str = "7d", from_date: str | None = None, to_date: str | None = None) -> dict:
    start, end, days = period_range(period, from_date, to_date)
    previous_start = start - (end - start)
    previous_end = start
    payments = db.query(Payment).filter(Payment.created_at >= start, Payment.created_at < end).all()
    previous_payments = db.query(Payment).filter(Payment.created_at >= previous_start, Payment.created_at < previous_end).all()
    checkout_records = checkout_intelligence._records(db, iso(start), iso(end))
    previous_checkout_records = checkout_intelligence._records(db, iso(previous_start), iso(previous_end))
    payment_metrics = _payment_metrics(payments)
    previous_payment_metrics = _payment_metrics(previous_payments)
    checkout_metrics = _checkout_metrics(checkout_records)
    previous_checkout_metrics = _checkout_metrics(previous_checkout_records)
    payment_metrics["has_data"] = bool(payments)
    previous_payment_metrics["has_data"] = bool(previous_payments)
    checkout_metrics["has_data"] = bool(checkout_records)
    previous_checkout_metrics["has_data"] = bool(previous_checkout_records)

    anomaly_rows = db.query(Anomaly).filter(Anomaly.anomaly_type.in_(ANOMALY_TYPES), Anomaly.detected_at >= start, Anomaly.detected_at < end).order_by(Anomaly.detected_at.desc()).all()
    anomaly_counts = Counter(row.severity for row in anomaly_rows)
    recovery_rows = db.query(RecoveryAction).filter(RecoveryAction.created_at >= start, RecoveryAction.created_at < end).all()
    payment_ids = {row.payment_id for row in payments}
    recovery_rows = [row for row in recovery_rows if row.payment_id.startswith("checkout:") or row.payment_id in payment_ids]
    recovery_counts = Counter(row.status for row in recovery_rows)
    event_rows = db.query(CheckoutEvent).filter(CheckoutEvent.created_at >= start, CheckoutEvent.created_at < end).all()
    checkout_failures = Counter((event.error_reason or event.event_type) for event in event_rows if event.event_type in {"payment_failed", "otp_failed"})

    summary = {
        **{key: payment_metrics[key] for key in ("total_payments", "successful_payments", "failed_payments", "payment_volume", "success_rate")},
        **checkout_metrics,
        "recovery_opportunities": len(recovery_rows),
        "completed_recovery_actions": recovery_counts["completed"] + recovery_counts["executed"],
        "detected_anomalies": len(anomaly_rows),
    }
    comparisons = {
        "payment_volume": _comparison(payment_metrics, previous_payment_metrics, "payment_volume"),
        "success_rate": _comparison(payment_metrics, previous_payment_metrics, "success_rate"),
        "checkout_conversion": _comparison(checkout_metrics, previous_checkout_metrics, "conversion_rate"),
    }
    return {
        "period": period if period in {"today", "7d", "30d"} else "custom",
        "range": {"from": iso(start), "to": iso(end)},
        "has_data": bool(payments or checkout_records or anomaly_rows or recovery_rows),
        "summary": summary,
        "payments": {**payment_metrics, "failure_reasons": _failure_reasons(db, start, end), "method_performance": _method_performance(db, start, end)},
        "checkout": {**checkout_metrics, "failure_reasons": [{"name": name, "count": count} for name, count in checkout_failures.most_common(10)]},
        "anomalies": {
            "total": len(anomaly_rows), "critical": anomaly_counts["critical"], "high": anomaly_counts["high"], "medium": anomaly_counts["medium"],
            "types": dict(Counter(row.anomaly_type for row in anomaly_rows)),
            "recent": [{"id": str(row.id), "type": row.anomaly_type, "severity": row.severity, "detected_at": iso(row.detected_at)} for row in anomaly_rows[:10]],
        },
        "recovery": {
            "opportunities": len(recovery_rows), "high_priority": sum(row.risk in {"high", "critical"} for row in recovery_rows),
            "medium_priority": sum(row.risk == "medium" for row in recovery_rows), "completed": summary["completed_recovery_actions"],
            "recommended": recovery_counts["recommended"] + recovery_counts["pending"] + recovery_counts["in_progress"], "dismissed": recovery_counts["dismissed"] + recovery_counts["ignored"],
        },
        "trends": {"payments": _payment_trend(payments), "checkout": _checkout_trend(checkout_records), "recovery": [{"name": key, "value": value} for key, value in recovery_counts.items()]},
        "failure_reasons": _failure_reasons(db, start, end),
        "comparisons": comparisons,
        "comparison_label": f"vs previous {days} day(s)",
    }
