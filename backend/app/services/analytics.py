from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..models import (
    CheckoutEvent,
    CheckoutSession,
    Payment,
    PaymentEvent,
    UpiMandate,
)
from ..utils.cache import ttl_cache
from ..utils.helpers import iso, resolve_range, to_float

SUCCESS_STATUSES = ("success", "captured", "authorized")
FAILED_STATUSES = ("failed", "attempted")


@ttl_cache(ttl=20.0)
def compute_summary(db: Session, from_date: str | None, to_date: str | None) -> dict:
    start, end = resolve_range(from_date, to_date)

    payments_q = db.query(Payment).filter(Payment.created_at >= start, Payment.created_at < end)

    total_txns = payments_q.count()
    volume = (
        payments_q.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
    )
    succeeded = payments_q.filter(Payment.status.in_(SUCCESS_STATUSES)).count()
    failed = payments_q.filter(Payment.status.in_(FAILED_STATUSES)).count()

    success_rate = (succeeded / (succeeded + failed) * 100) if (succeeded + failed) else None

    amount_at_risk = (
        payments_q.filter(Payment.status.in_(FAILED_STATUSES))
        .with_entities(func.coalesce(func.sum(Payment.amount), 0))
        .scalar()
        or 0
    )

    # UPI failure rate (live UPI payment rows in the window)
    upi_succeeded = payments_q.filter(Payment.method == "upi", Payment.status.in_(SUCCESS_STATUSES)).count()
    upi_failed = payments_q.filter(Payment.method == "upi", Payment.status.in_(FAILED_STATUSES)).count()
    upi_rate = (upi_failed / (upi_failed + upi_succeeded) * 100) if (upi_failed + upi_succeeded) else None

    # Amount already recovered via successful recovery outcomes
    recovered = _recovered_amount(db)

    # Checkout abandonment (% of sessions that ended abandoned)
    sessions_q = db.query(CheckoutSession).filter(
        CheckoutSession.started_at >= start, CheckoutSession.started_at < end
    )
    sessions_started = sessions_q.count()
    sessions_abandoned = sessions_q.filter(CheckoutSession.status == "abandoned").count()
    checkout_abandonment = (sessions_abandoned / sessions_started * 100) if sessions_started else None

    # Mandate health (% of mandates currently active out of those that reached a decision)
    mandate_q = db.query(UpiMandate).filter(
        UpiMandate.created_at >= start, UpiMandate.created_at < end
    )
    mandate_active = mandate_q.filter(UpiMandate.status == "active").count()
    mandate_failed = mandate_q.filter(UpiMandate.status.in_(("failed", "rejected"))).count()
    mandate_health = (
        (mandate_active / (mandate_active + mandate_failed) * 100)
        if (mandate_active + mandate_failed)
        else None
    )
    mandate_failure_rate = (
        (mandate_failed / (mandate_active + mandate_failed) * 100)
        if (mandate_active + mandate_failed)
        else None
    )

    risk_amount = to_float(amount_at_risk) or 0
    recovery_rate = (
        (recovered / (recovered + risk_amount) * 100) if recovered else None
    )

    return {
        "volume": to_float(volume),
        "transactions": total_txns,
        "success_rate": round(success_rate, 1) if success_rate is not None else None,
        "failed": failed,
        "amount_at_risk": to_float(amount_at_risk),
        "checkout_abandonment": round(checkout_abandonment, 1) if checkout_abandonment is not None else None,
        "mandate_health": round(mandate_health, 1) if mandate_health is not None else None,
        "mandate_failure_rate": round(mandate_failure_rate, 1) if mandate_failure_rate is not None else None,
        "upi_failure_rate": round(upi_rate, 1) if upi_rate is not None else None,
        "recovered_amount": to_float(recovered),
        "recovery_rate": round(recovery_rate, 1) if recovery_rate is not None else None,
    }


def _recovered_amount(db: Session) -> float:
    """Total amount resolved through successful recovery outcomes."""
    from ..models import RecoveryAction, RecoveryOutcome

    rows = (
        db.query(RecoveryOutcome, RecoveryAction.amount)
        .join(RecoveryAction, RecoveryAction.id == RecoveryOutcome.recovery_action_id)
        .filter(RecoveryOutcome.result == "success")
        .all()
    )
    return sum(to_float(amount) or 0 for _, amount in rows)


@ttl_cache(ttl=20.0)
def failure_breakdown(db: Session, from_date: str | None, to_date: str | None, limit: int = 12) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    q = (
        db.query(Payment.failure_reason, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .group_by(Payment.failure_reason)
        .order_by(func.count(Payment.id).desc())
        .limit(limit)
        .all()
    )
    total = sum(r[1] for r in q) or 1
    return [
        {
            "reason": r[0] or "unknown",
            "code": r[0],
            "count": r[1],
            "percent": round(r[1] / total * 100, 1),
            "amount": to_float(r[2]),
        }
        for r in q
    ]


@ttl_cache(ttl=20.0)
def failure_code_breakdown(db: Session, from_date: str | None, to_date: str | None, limit: int = 12) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    q = (
        db.query(Payment.failure_code, func.count(Payment.id))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .group_by(Payment.failure_code)
        .order_by(func.count(Payment.id).desc())
        .limit(limit)
        .all()
    )
    return [{"code": r[0] or "unknown", "count": r[1]} for r in q]


@ttl_cache(ttl=20.0)
def method_distribution(db: Session, from_date: str | None, to_date: str | None) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    q = (
        db.query(Payment.method, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.created_at >= start, Payment.created_at < end, Payment.method.isnot(None))
        .group_by(Payment.method)
        .order_by(func.count(Payment.id).desc())
        .all()
    )
    total = sum(r[1] for r in q) or 1
    return [
        {"name": r[0] or "unknown", "count": r[1], "percent": round(r[1] / total * 100, 1), "amount": to_float(r[2])}
        for r in q
    ]


@ttl_cache(ttl=20.0)
def payment_series(
    db: Session, from_date: str | None, to_date: str | None, group: str = "day"
) -> list[dict]:
    start, end = resolve_range(from_date, to_date)
    bucket = func.date(Payment.created_at) if group == "day" else func.strftime("%Y-%m", Payment.created_at)
    q = (
        db.query(
            bucket.label("period"),
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0),
            func.sum(case((Payment.status.in_(SUCCESS_STATUSES), 1), else_=0)),
            func.sum(case((Payment.status.in_(FAILED_STATUSES), 1), else_=0)),
        )
        .filter(Payment.created_at >= start, Payment.created_at < end)
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    out = []
    for period, count, amount, ok, bad in q:
        out.append(
            {
                "period": iso(period) if period else None,
                "date": iso(period) if period else None,
                "count": count,
                "volume": to_float(amount),
                "success": ok,
                "failed": bad,
                "success_rate": round(ok / count * 100, 1) if count else None,
            }
        )
    return out


@ttl_cache(ttl=20.0)
def mandate_stats(db: Session, from_date: str | None, to_date: str | None) -> dict:
    start, end = resolve_range(from_date, to_date)
    q = db.query(UpiMandate).filter(UpiMandate.created_at >= start, UpiMandate.created_at < end)
    total = q.count()
    active = q.filter(UpiMandate.status == "active").count()
    failed = q.filter(UpiMandate.status.in_(("failed", "rejected"))).count()
    pending = q.filter(UpiMandate.status.in_(("pending", "processing", "attempted"))).count()
    rate = (active / total * 100) if total else None
    return {
        "total": total,
        "active": active,
        "failed": failed,
        "pending": pending,
        "success_rate": round(rate, 1) if rate is not None else None,
    }


@ttl_cache(ttl=20.0)
def checkout_analytics(db: Session, from_date: str | None, to_date: str | None) -> dict:
    start, end = resolve_range(from_date, to_date)

    # funnel counts from checkout events (session telemetry)
    stages = [
        "checkout_started",
        "payment_method_selected",
        "payment_initiated",
        "otp_started",
        "otp_completed",
        "payment_completed",
    ]
    stage_counts = {}
    for st in stages:
        n = (
            db.query(func.count(func.distinct(CheckoutEvent.session_id)))
            .filter(
                CheckoutEvent.event_type == st,
                CheckoutEvent.created_at >= start,
                CheckoutEvent.created_at < end,
            )
            .scalar()
            or 0
        )
        stage_counts[st] = n

    started = stage_counts.get("checkout_started", 0)
    completed = stage_counts.get("payment_completed", 0)

    # funnel with value = % of checkout_started, count = distinct sessions
    funnel = []
    for i, st in enumerate(stages):
        count = stage_counts.get(st, 0)
        funnel.append(
            {
                "stage": st,
                "stage_index": i,
                "label": st,
                "count": count,
                "value": round(count / started * 100, 1) if started else 0,
            }
        )

    # signals
    page_reloads = _extra_started(db, start, end)
    otp_attempts = (
        db.query(func.count(CheckoutEvent.id))
        .filter(CheckoutEvent.event_type == "otp_started", CheckoutEvent.created_at >= start, CheckoutEvent.created_at < end)
        .scalar()
        or 0
    )
    otp_completed = (
        db.query(func.count(CheckoutEvent.id))
        .filter(CheckoutEvent.event_type == "otp_completed", CheckoutEvent.created_at >= start, CheckoutEvent.created_at < end)
        .scalar()
        or 0
    )
    payment_retries = (
        db.query(func.count(CheckoutEvent.id))
        .filter(CheckoutEvent.event_type == "payment_retry", CheckoutEvent.created_at >= start, CheckoutEvent.created_at < end)
        .scalar()
        or 0
    )
    methods_attempted = (
        db.query(func.count(func.distinct(CheckoutEvent.method)))
        .filter(
            CheckoutEvent.event_type == "payment_method_selected",
            CheckoutEvent.method.isnot(None),
            CheckoutEvent.created_at >= start,
            CheckoutEvent.created_at < end,
        )
        .scalar()
        or 0
    )

    sessions_q = db.query(CheckoutSession).filter(
        CheckoutSession.started_at >= start, CheckoutSession.started_at < end
    )
    all_sessions = sessions_q.count()
    avg_duration = (
        sessions_q.with_entities(func.avg(CheckoutSession.duration_seconds)).scalar()
        if all_sessions
        else None
    )

    # drop-off by method: sessions started with a method vs completed for that method
    method_rows = (
        db.query(CheckoutEvent.method, func.count(func.distinct(CheckoutEvent.session_id)))
        .filter(
            CheckoutEvent.event_type == "payment_method_selected",
            CheckoutEvent.method.isnot(None),
            CheckoutEvent.created_at >= start,
            CheckoutEvent.created_at < end,
        )
        .group_by(CheckoutEvent.method)
        .all()
    )
    completed_rows = (
        db.query(CheckoutEvent.method, func.count(func.distinct(CheckoutEvent.session_id)))
        .filter(
            CheckoutEvent.event_type == "payment_completed",
            CheckoutEvent.method.isnot(None),
            CheckoutEvent.created_at >= start,
            CheckoutEvent.created_at < end,
        )
        .group_by(CheckoutEvent.method)
        .all()
    )
    comp = dict(completed_rows)
    dropoff_by_method = []
    for method, selected in method_rows:
        c = comp.get(method, 0)
        drop = selected - c
        dropoff_by_method.append(
            {
                "name": method,
                "method": method,
                "count": drop,
                "value": round(drop / selected * 100, 1) if selected else 0,
            }
        )
    dropoff_by_method.sort(key=lambda x: x["count"], reverse=True)

    # drop-off by device: sessions started per device vs sessions abandoned per device
    dev_start = (
        db.query(CheckoutSession.device, func.count(CheckoutSession.id))
        .filter(CheckoutSession.started_at >= start, CheckoutSession.started_at < end)
        .group_by(CheckoutSession.device)
        .all()
    )
    dev_abandoned = (
        db.query(CheckoutSession.device, func.count(CheckoutSession.id))
        .filter(
            CheckoutSession.status == "abandoned",
            CheckoutSession.started_at >= start,
            CheckoutSession.started_at < end,
        )
        .group_by(CheckoutSession.device)
        .all()
    )
    abandon = dict(dev_abandoned)
    dropoff_by_device = []
    for device, started_count in dev_start:
        ab = abandon.get(device, 0)
        dropoff_by_device.append(
            {"device": device or "unknown", "name": device or "unknown", "count": ab, "value": ab}
        )
    dropoff_by_device.sort(key=lambda x: x["count"], reverse=True)

    # drop-off trend (per day)
    days = db.query(func.date(CheckoutSession.started_at), CheckoutSession.status, func.count(CheckoutSession.id)).filter(
        CheckoutSession.started_at >= start, CheckoutSession.started_at < end
    ).group_by(func.date(CheckoutSession.started_at), CheckoutSession.status).all()
    per_day: dict[str, dict] = {}
    for day, status, cnt in days:
        day_key = day.isoformat() if hasattr(day, "isoformat") else str(day) if day else "?"
        d = per_day.setdefault(day_key, {"started": 0, "abandoned": 0})
        d["started"] += cnt
        if status == "abandoned":
            d["abandoned"] += cnt
    dropoff_trend = [
        {"date": day, "dropoff_rate": round(d["abandoned"] / d["started"] * 100, 1) if d["started"] else 0}
        for day, d in sorted(per_day.items())
    ]

    signals = {
        "avg_time_on_checkout": round(avg_duration, 1) if avg_duration is not None else None,
        "page_reloads": page_reloads,
        "methods_attempted": methods_attempted,
        "otp_attempts": otp_attempts,
        "otp_completion": otp_completed,
        "payment_retries": payment_retries,
    }

    conversion_rate = (completed / started * 100) if started else None

    investigation = {
        "signal_summary": (
            f"{started} customers started checkout, {completed} completed "
            f"({round(conversion_rate, 1) if conversion_rate is not None else 0}%). "
            f"{payment_retries} retries, {otp_attempts} OTP attempts, {page_reloads} reloads."
        )
        if started
        else "No checkout sessions recorded in this window.",
        "likely_cause": _checkout_likely_cause(signals, conversion_rate, started),
        "confidence": _checkout_confidence(started),
        "recommended_intervention": (
            "Investigate the OTP/authentication provider and the abandon-heavy payment methods; "
            "surface retry prompts for transient failures."
            if started
            else "Wire checkout session telemetry to POST /api/webhooks/checkout to enable investigation."
        ),
    }

    return {
        "conversion_rate": round(conversion_rate, 1) if conversion_rate is not None else None,
        "funnel": funnel,
        "signals": signals,
        "dropoff_by_method": dropoff_by_method,
        "dropoff_by_device": dropoff_by_device,
        "dropoff_trend": dropoff_trend,
        "investigation": investigation,
    }


def _extra_started(db: Session, start: datetime, end: datetime) -> int:
    """Number of sessions that sent more than one checkout_started (page reloads)."""
    rows = (
        db.query(CheckoutEvent.session_id, func.count(CheckoutEvent.id))
        .filter(
            CheckoutEvent.event_type == "checkout_started",
            CheckoutEvent.created_at >= start,
            CheckoutEvent.created_at < end,
        )
        .group_by(CheckoutEvent.session_id)
        .having(func.count(CheckoutEvent.id) > 1)
        .all()
    )
    return len(rows)


def _checkout_likely_cause(signals: dict, conversion_rate: float | None, started: int) -> str:
    if not started:
        return "No checkout sessions to evaluate yet."
    causes = []
    otp_attempts = signals.get("otp_attempts") or 0
    otp_completed = signals.get("otp_completion") or 0
    retries = signals.get("payment_retries") or 0
    if otp_completed < otp_attempts:
        causes.append("OTP friction: OTP was started more often than it completed")
    if retries >= 3:
        causes.append("payment providers returned transient failures prompting repeated retries")
    if signals.get("page_reloads", 0) >= 3:
        causes.append("page reloads indicate a display/authorization issue on checkout")
    if conversion_rate is not None and conversion_rate < 40:
        causes.append("overall conversion is low relative to the baseline funnel")
    return "; ".join(causes[:3]) or "No dominant friction signal — drop-offs are spread across stages."


def _checkout_confidence(started: int) -> int:
    if started == 0:
        return 0
    if started < 10:
        return 55
    if started < 50:
        return 75
    return 90