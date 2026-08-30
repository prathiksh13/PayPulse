from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Anomaly, CheckoutSession, Payment
from ..utils.helpers import now_utc, previous_period, resolve_range, to_float

SUCCESS_STATUSES = ("success", "captured", "authorized")
FAILED_STATUSES = ("failed", "attempted")
MIN_BASELINE_RECORDS = 3
# Kept as a read-only compatibility constant for the existing AI Agent.
MIN_TRANSACTIONS = 2
RATE_MULTIPLIER = 1.5
MIN_RATE_POINT_CHANGE = 10.0


def _minimum_records() -> int:
    return max(MIN_BASELINE_RECORDS, settings.anomaly_min_transactions)


def _payment_stats(db: Session, start, end) -> dict:
    rows = (
        db.query(Payment.status, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.created_at >= start, Payment.created_at < end)
        .group_by(Payment.status)
        .all()
    )
    total = sum(row[1] for row in rows)
    succeeded = sum(row[1] for row in rows if row[0] in SUCCESS_STATUSES)
    failed = sum(row[1] for row in rows if row[0] in FAILED_STATUSES)
    failed_amount = sum(to_float(row[2]) or 0 for row in rows if row[0] in FAILED_STATUSES)
    return {
        "total": total,
        "observed": succeeded + failed,
        "succeeded": succeeded,
        "failed": failed,
        "failure_rate": failed / (succeeded + failed) * 100 if succeeded + failed else None,
        "success_rate": succeeded / (succeeded + failed) * 100 if succeeded + failed else None,
        "amount_at_risk": failed_amount,
    }


def _method_stats(db: Session, start, end) -> dict[str, dict]:
    rows = (
        db.query(Payment.method, Payment.status, func.count(Payment.id))
        .filter(Payment.created_at >= start, Payment.created_at < end, Payment.method.isnot(None))
        .group_by(Payment.method, Payment.status)
        .all()
    )
    stats: dict[str, dict] = {}
    for method, status, count in rows:
        item = stats.setdefault(method, {"total": 0, "failed": 0})
        if status in SUCCESS_STATUSES or status in FAILED_STATUSES:
            item["total"] += count
        if status in FAILED_STATUSES:
            item["failed"] += count
    for item in stats.values():
        item["rate"] = item["failed"] / item["total"] * 100 if item["total"] else None
    return stats


def _checkout_stats(db: Session, start, end) -> dict:
    rows = (
        db.query(CheckoutSession.status, func.count(CheckoutSession.id))
        .filter(CheckoutSession.started_at >= start, CheckoutSession.started_at < end)
        .group_by(CheckoutSession.status)
        .all()
    )
    started = sum(row[1] for row in rows)
    completed = sum(row[1] for row in rows if row[0] == "completed")
    abandoned = sum(row[1] for row in rows if row[0] == "abandoned")
    return {
        "started": started,
        "completed": completed,
        "abandoned": abandoned,
        "conversion_rate": completed / started * 100 if started else None,
        "abandonment_rate": abandoned / started * 100 if started else None,
    }


def _failure_patterns(db: Session, start, end) -> list[dict]:
    rows = (
        db.query(Payment.failure_reason, Payment.method, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.status.in_(FAILED_STATUSES), Payment.created_at >= start, Payment.created_at < end)
        .group_by(Payment.failure_reason, Payment.method)
        .order_by(func.count(Payment.id).desc())
        .limit(10)
        .all()
    )
    return [
        {"failure_reason": reason or "unknown", "method": method or "unknown", "count": count, "amount": to_float(amount) or 0}
        for reason, method, count, amount in rows
    ]


def _percent_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return round((current - baseline) / abs(baseline) * 100, 2)


def _candidate(anomaly_type, severity, title, description, metric, current, baseline, affected, supporting):
    return {
        "type": anomaly_type,
        "severity": severity,
        "title": title,
        "description": description,
        "metric": metric,
        "current": round(current, 2),
        "baseline": round(baseline, 2),
        "change_percent": _percent_change(current, baseline),
        "affected": affected,
        "supporting": supporting,
    }


def detect(db: Session, from_date: str | None = None, to_date: str | None = None) -> tuple[list[dict], list[str]]:
    start, end = resolve_range(from_date, to_date)
    previous_start, previous_end = previous_period(start, end)
    minimum = _minimum_records()
    candidates: list[dict] = []
    insufficient: list[str] = []

    current = _payment_stats(db, start, end)
    baseline = _payment_stats(db, previous_start, previous_end)
    if current["observed"] < minimum or baseline["observed"] < minimum:
        insufficient.append("payment_rate_baseline")
    else:
        current_failure = current["failure_rate"] or 0
        baseline_failure = baseline["failure_rate"] or 0
        if current["failed"] >= settings.anomaly_min_transactions and (
            current_failure >= max(50, baseline_failure * RATE_MULTIPLIER)
        ):
            candidates.append(_candidate(
                "payment_failure_spike", "critical" if current_failure >= 75 else "high",
                "Payment failure spike",
                f"Payment failure rate increased to {current_failure:.1f}% from a historical baseline of {baseline_failure:.1f}%.",
                "failure_rate_percent", current_failure, baseline_failure, current["failed"],
                [{"status": "failed", "count": current["failed"], "amount": current["amount_at_risk"]}],
            ))
        current_success = current["success_rate"] or 0
        baseline_success = baseline["success_rate"] or 0
        if current_success <= baseline_success - MIN_RATE_POINT_CHANGE:
            candidates.append(_candidate(
                "payment_success_rate_drop", "critical" if current_success < 25 else "high",
                "Payment success rate drop",
                f"Payment success rate fell to {current_success:.1f}% from a baseline of {baseline_success:.1f}%.",
                "success_rate_percent", current_success, baseline_success, current["failed"],
                [{"status": "success", "count": current["succeeded"]}, {"status": "failed", "count": current["failed"]}],
            ))

    methods = _method_stats(db, start, end)
    baseline_methods = _method_stats(db, previous_start, previous_end)
    eligible_methods = [m for m, item in methods.items() if item["total"] >= minimum and baseline_methods.get(m, {}).get("total", 0) >= minimum]
    if not eligible_methods:
        insufficient.append("payment_method_baseline")
    else:
        peer_rates = [methods[m]["rate"] for m in eligible_methods if methods[m]["rate"] is not None]
        peer_average = sum(peer_rates) / len(peer_rates) if peer_rates else None
        for method in eligible_methods:
            item = methods[method]
            historical = baseline_methods[method].get("rate") or 0
            if item["rate"] is not None and peer_average is not None and item["rate"] >= peer_average + MIN_RATE_POINT_CHANGE and item["rate"] >= max(30, historical * RATE_MULTIPLIER):
                candidates.append(_candidate(
                    "payment_method_anomaly", "high" if item["rate"] >= 60 else "medium",
                    f"{method.upper()} payment-method anomaly",
                    f"{method.upper()} has a {item['rate']:.1f}% failure rate versus a peer average of {peer_average:.1f}%.",
                    "method_failure_rate_percent", item["rate"], peer_average, item["failed"],
                    [{"method": method, "count": item["total"], "failed": item["failed"]}, {"peer_average_rate": round(peer_average, 2)}],
                ))

    checkout = _checkout_stats(db, start, end)
    checkout_baseline = _checkout_stats(db, previous_start, previous_end)
    if checkout["started"] < minimum or checkout_baseline["started"] < minimum:
        insufficient.append("checkout_dropoff_baseline")
    else:
        current_drop = checkout["abandonment_rate"] or 0
        baseline_drop = checkout_baseline["abandonment_rate"] or 0
        if current_drop >= max(25, baseline_drop * RATE_MULTIPLIER) and current_drop >= baseline_drop + MIN_RATE_POINT_CHANGE:
            candidates.append(_candidate(
                "checkout_dropoff_spike", "critical" if current_drop >= 75 else "high",
                "Checkout drop-off spike",
                f"Checkout abandonment increased to {current_drop:.1f}% from a baseline of {baseline_drop:.1f}%.",
                "abandonment_rate_percent", current_drop, baseline_drop, checkout["abandoned"],
                [{"started": checkout["started"], "abandoned": checkout["abandoned"]}],
            ))

    patterns = _failure_patterns(db, start, end)
    baseline_patterns = _failure_patterns(db, previous_start, previous_end)
    if not patterns or baseline["failed"] < minimum:
        insufficient.append("repeated_failure_baseline")
    else:
        baseline_counts = {
            (item["failure_reason"], item["method"]): item["count"]
            for item in baseline_patterns
        }
        for item in patterns:
            key = (item["failure_reason"], item["method"])
            if item["count"] >= settings.anomaly_min_transactions and item["count"] >= max(3, baseline_counts.get(key, 0) * 2):
                candidates.append(_candidate(
                    "repeated_failure_pattern", "high" if item["count"] >= 5 else "medium",
                    "Repeated payment failure pattern",
                    f"{item['count']} failures share reason '{item['failure_reason']}' and method '{item['method']}'.",
                    "matching_failure_count", item["count"], baseline_counts.get(key, 0), item["count"], [item],
                ))
    return candidates, sorted(set(insufficient))


def detect_with_status(db: Session, from_date: str | None = None, to_date: str | None = None) -> tuple[list[Anomaly], list[str]]:
    candidates, insufficient = detect(db, from_date, to_date)
    today = now_utc().date()
    day_start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    stored = []
    for item in candidates:
        existing = db.query(Anomaly).filter(
            Anomaly.anomaly_type == item["type"], Anomaly.detected_at >= day_start,
            Anomaly.detected_at < day_end, Anomaly.status == "active",
        ).first()
        if existing is None:
            existing = Anomaly(anomaly_type=item["type"], status="active", detected_at=now_utc())
            db.add(existing)
        existing.severity = item["severity"]
        existing.metric_current = item["current"]
        existing.metric_baseline = item["baseline"]
        existing.affected_transactions = item["affected"]
        existing.amount_at_risk = next(
            (e.get("amount") for e in item["supporting"] if isinstance(e, dict) and e.get("amount") is not None),
            0,
        )
        existing.likely_cause = item["description"]
        existing.ai_explanation = [item["title"], item["description"], {"metric": item["metric"], "supporting_data": item["supporting"]}]
        stored.append(existing)
    db.commit()
    return stored, insufficient


def detect_and_store(db: Session, from_date: str | None = None, to_date: str | None = None) -> list[Anomaly]:
    return detect_with_status(db, from_date, to_date)[0]


def resolve_anomaly(db: Session, anomaly_id: int) -> Anomaly | None:
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if anomaly and anomaly.status == "active":
        anomaly.status = "resolved"
        anomaly.resolved_at = now_utc()
        db.commit()
    return anomaly
