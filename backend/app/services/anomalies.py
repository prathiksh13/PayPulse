from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Anomaly, CheckoutSession, Payment, UpiMandate, CheckoutEvent
from ..utils.helpers import now_utc, previous_period, resolve_range, to_float
from ..utils.plog import plog

FAILED_STATUSES = ("failed", "attempted")

# method -> anomaly type naming the frontend understands
METHOD_ANOMALY_TYPES = {
    "upi": "upi_failure_spike",
    "card": "card_failure_spike",
    "netbanking": "payment_failure_spike",
    "wallet": "payment_failure_spike",
}

MIN_TRANSACTIONS = 2            # default; overridden by settings.anomaly_min_transactions
FAILURE_RATE_MULTIPLIER = 2.5  # current window must exceed baseline rate by this factor
CHECKOUT_RATE_DROP = 0.5       # current conversion below 50% of baseline


def _min_tx() -> int:
    return settings.anomaly_min_transactions


def _failure_stats(db: Session, start, end):
    q = (
        db.query(Payment.method, func.count(Payment.id))
        .filter(Payment.created_at >= start, Payment.created_at < end)
        .group_by(Payment.method)
        .all()
    )
    fq = (
        db.query(Payment.method, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .group_by(Payment.method)
        .all()
    )
    totals = {m: c for m, c in q}
    failures = {m: {"count": c, "amount": to_float(a)} for m, c, a in fq}
    stats = {}
    for method, total in totals.items():
        f = failures.get(method, {"count": 0, "amount": 0})
        stats[method] = {
            "total": total,
            "failed": f["count"],
            "rate": round(f["count"] / total * 100, 2) if total else 0,
            "amount_at_risk": f["amount"],
        }
    return stats


def _checkout_stats(db: Session, start, end):
    started = (
        db.query(func.count(CheckoutSession.id))
        .filter(CheckoutSession.started_at >= start, CheckoutSession.started_at < end)
        .scalar()
        or 0
    )
    completed = (
        db.query(func.count(CheckoutSession.id))
        .filter(CheckoutSession.status == "completed", CheckoutSession.started_at >= start, CheckoutSession.started_at < end)
        .scalar()
        or 0
    )
    return {"started": started, "completed": completed, "rate": round(completed / started * 100, 2) if started else 0}


def _mandate_stats(db: Session, start, end):
    total = (
        db.query(func.count(UpiMandate.id))
        .filter(UpiMandate.created_at >= start, UpiMandate.created_at < end)
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(UpiMandate.id))
        .filter(
            UpiMandate.status.in_(("failed", "rejected")),
            UpiMandate.created_at >= start,
            UpiMandate.created_at < end,
        )
        .scalar()
        or 0
    )
    return {"total": total, "failed": failed, "rate": round(failed / total * 100, 2) if total else 0}


def _append_overall_spike(candidates: list[dict], total_cur: dict, total_base_rate: float, min_tx: int, method_spikes: set):
    affected_methods = sorted(method_spikes) if method_spikes else "multiple methods"
    candidates.append(
        {
            "type": "payment_failure_spike",
            "severity": "critical" if total_cur["rate"] >= 50 or total_cur["failed"] >= 20 else "high",
            "affected_method": None,
            "current": total_cur["rate"],
            "baseline": total_base_rate,
            "affected": total_cur["failed"],
            "amount_at_risk": total_cur["amount_at_risk"],
            "cause": (
                f"{total_cur['failed']} payments failed across {affected_methods} in this window "
                f"({total_cur['rate']}%) vs a baseline of {total_base_rate}%."
            ),
        }
    )


def detect_and_store(db: Session, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    """Detect anomalies from real DB statistics and persist new ones once per day per type."""
    start, end = resolve_range(from_date, to_date)
    prev_start, prev_end = previous_period(start, end)
    min_tx = _min_tx()

    candidates: list[dict] = []

    # 1. failure spikes per payment method
    current = _failure_stats(db, start, end)
    baseline = _failure_stats(db, prev_start, prev_end)
    for method, cur in current.items():
        if cur["failed"] < min_tx:
            continue
        base = baseline.get(method, {})
        base_rate = base.get("rate", 0)
        threshold = (base_rate * FAILURE_RATE_MULTIPLIER) if base_rate > 0 else 0
        if cur["rate"] > threshold or (base_rate == 0 and cur["rate"] >= 50):
            name = METHOD_ANOMALY_TYPES.get(method, "payment_failure_spike")
            severity = "critical" if cur["rate"] >= 50 or cur["failed"] >= 20 else "high"
            candidates.append(
                {
                    "type": name,
                    "severity": severity,
                    "affected_method": method,
                    "current": cur["rate"],
                    "baseline": base_rate,
                    "affected": cur["failed"],
                    "amount_at_risk": cur["amount_at_risk"],
                    "cause": (
                        f"{cur['failed']} {method.upper()} payments failed in this window "
                        f"({cur['rate']}%) vs a baseline of {base_rate}%."
                    ),
                }
            )

    # 1b. overall failure spike across all methods (fires even when the failed
    #     methods are spread out and no single method crosses the threshold)
    total_cur = {
        "failed": sum(c["failed"] for c in current.values()),
        "total": sum(c["total"] for c in current.values()),
        "amount_at_risk": sum(c["amount_at_risk"] for c in current.values()),
    }
    total_base = {
        "failed": sum(c["failed"] for c in baseline.values()),
        "total": sum(c["total"] for c in baseline.values()),
    }
    total_base_rate = 0
    if total_cur["total"]:
        total_cur["rate"] = round(total_cur["failed"] / total_cur["total"] * 100, 2)
        total_base_rate = round(total_base["failed"] / total_base["total"] * 100, 2) if total_base["total"] else 0
        if total_cur["failed"] >= min_tx and (
            (total_base["total"] == 0 and total_cur["rate"] >= 50)
            or (total_base["total"] > 0 and total_cur["rate"] > total_base_rate * FAILURE_RATE_MULTIPLIER)
        ):
            method_spikes = {c["affected_method"] for c in candidates if c["affected_method"]}
            if method_spikes:
                already_covered = sum(c["affected"] for c in candidates if c["affected"] is not None)
                if already_covered >= total_cur["failed"]:
                    pass  # all failures already attributed to method-level spikes
                else:
                    _append_overall_spike(candidates, total_cur, total_base_rate, min_tx, method_spikes)
            else:
                _append_overall_spike(candidates, total_cur, total_base_rate, min_tx, set())
    plog(f"ANOMALY_STATS failed={total_cur.get('failed', 0)} total={total_cur.get('total', 0)} "
         f"rate={total_cur.get('rate', 0)} baseline_rate={total_base_rate if total_base.get('total') else 0} "
         f"min_tx={min_tx} candidates={len(candidates)}")

    # 2. provider timeout spikes
    timeout_cur = (
        db.query(func.count(Payment.id))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.failure_reason.ilike("%timeout%"),
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .scalar()
        or 0
    )
    timeout_base = (
        db.query(func.count(Payment.id))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.failure_reason.ilike("%timeout%"),
            Payment.created_at >= prev_start,
            Payment.created_at < prev_end,
        )
        .scalar()
        or 0
    )
    if timeout_cur >= min_tx and timeout_cur > timeout_base * FAILURE_RATE_MULTIPLIER:
        candidates.append(
            {
                "type": "provider_timeout_increase",
                "severity": "high",
                "affected_method": None,
                "current": timeout_cur,
                "baseline": timeout_base,
                "affected": timeout_cur,
                "amount_at_risk": _timeout_at_risk(db, start, end),
                "cause": (
                    f"{timeout_cur} payment failures mention bank/provider timeouts this window "
                    f"vs {timeout_base} in the baseline period."
                ),
            }
        )

    # 3. checkout conversion drop
    cc = _checkout_stats(db, start, end)
    cb = _checkout_stats(db, prev_start, prev_end)
    if cb["started"] >= min_tx and cc["rate"] < cb["rate"] * CHECKOUT_RATE_DROP and cc["rate"] < 50:
        candidates.append(
            {
                "type": "checkout_conversion_drop",
                "severity": "high",
                "affected_method": None,
                "current": cc["rate"],
                "baseline": cb["rate"],
                "affected": cc["started"] - cc["completed"],
                "amount_at_risk": _checkout_at_risk(db, start, end),
                "cause": (
                    f"Checkout conversion fell to {cc['rate']}% from a baseline of {cb['rate']}% "
                    f"({cc['started']} sessions this window)."
                ),
            }
        )

    # 4. mandate failure spike
    mc = _mandate_stats(db, start, end)
    mb = _mandate_stats(db, prev_start, prev_end)
    if mc["failed"] >= min_tx and (mc["rate"] > (mb["rate"] * FAILURE_RATE_MULTIPLIER) or (mb["rate"] == 0 and mc["rate"] >= 50)):
        candidates.append(
            {
                "type": "mandate_failure_spike",
                "severity": "high",
                "affected_method": "upi",
                "current": mc["rate"],
                "baseline": mb["rate"],
                "affected": mc["failed"],
                "amount_at_risk": _mandate_amount_at_risk(db, start, end),
                "cause": (
                    f"{mc['failed']} UPI mandate activations failed ({mc['rate']}%) "
                    f"vs a baseline of {mb['rate']}%."
                ),
            }
        )

    # 5. unusual retry rate (attempts > 1 grew)
    retry_cur = (
        db.query(func.count(Payment.id))
        .filter(Payment.attempt_count > 1, Payment.created_at >= start, Payment.created_at < end)
        .scalar()
        or 0
    )
    retry_base = (
        db.query(func.count(Payment.id))
        .filter(Payment.attempt_count > 1, Payment.created_at >= prev_start, Payment.created_at < prev_end)
        .scalar()
        or 0
    )
    if retry_cur >= min_tx and retry_cur > retry_base * FAILURE_RATE_MULTIPLIER:
        candidates.append(
            {
                "type": "unusual_retry_rate",
                "severity": "medium",
                "affected_method": None,
                "current": retry_cur,
                "baseline": retry_base,
                "affected": retry_cur,
                "amount_at_risk": 0,
                "cause": (
                    f"{retry_cur} payments required more than one attempt this window "
                    f"vs {retry_base} in the baseline period."
                ),
            }
        )

    detection_day = now_utc().date().isoformat()
    day_start = datetime.combine(now_utc().date(), time.min, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    stored: list[dict] = []
    for cand in candidates:
        existing = (
            db.query(Anomaly)
            .filter(
                Anomaly.anomaly_type == cand["type"],
                Anomaly.detected_at >= day_start,
                Anomaly.detected_at < day_end,
                Anomaly.status == "active",
            )
            .first()
        )
        if existing:
            # Keep one active anomaly per type/day, but refresh its metrics as
            # additional real payment events arrive.
            existing.severity = cand["severity"]
            existing.metric_current = cand["current"]
            existing.metric_baseline = cand["baseline"]
            existing.affected_transactions = cand["affected"]
            existing.amount_at_risk = cand["amount_at_risk"]
            existing.affected_method = cand["affected_method"]
            existing.likely_cause = cand["cause"]
            stored.append(existing)
            continue
        anomaly = Anomaly(
            anomaly_type=cand["type"],
            severity=cand["severity"],
            status="active",
            detected_at=now_utc(),
            metric_current=cand["current"],
            metric_baseline=cand["baseline"],
            affected_transactions=cand["affected"],
            amount_at_risk=cand["amount_at_risk"],
            affected_method=cand["affected_method"],
            likely_cause=cand["cause"],
            ai_explanation=[
                cand["cause"],
                "The agent recomputed baseline metrics from live payment webhook data for this detection window.",
            ],
            recommended_action=_recommended_action(cand["type"]),
        )
        db.add(anomaly)
        stored.append(anomaly)

    db.commit()

    db.execute(
        text(
            """
            DELETE FROM anomalies
            WHERE id NOT IN (
                SELECT MIN(id) FROM anomalies
                GROUP BY anomaly_type, CAST(detected_at AS DATE), status
            )
            """
        )
    )
    db.commit()
    return stored


def resolve_anomaly(db: Session, anomaly_id: int) -> Anomaly | None:
    a = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if a and a.status == "active":
        a.status = "resolved"
        a.resolved_at = now_utc()
        db.commit()
    return a


def _timeout_at_risk(db: Session, start, end):
    return to_float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.failure_reason.ilike("%timeout%"),
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .scalar()
        or 0
    )


def _checkout_at_risk(db: Session, start, end):
    payment_ids = [
        s.payment_id
        for s in db.query(CheckoutSession).filter(
            CheckoutSession.started_at >= start,
            CheckoutSession.started_at < end,
            CheckoutSession.payment_id.isnot(None),
        ).all()
    ]
    if not payment_ids:
        return 0.0
    return to_float(
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.payment_id.in_(payment_ids))
        .scalar()
        or 0
    )


def _mandate_amount_at_risk(db: Session, start, end):
    return to_float(
        db.query(func.coalesce(func.sum(UpiMandate.amount), 0))
        .filter(
            UpiMandate.status.in_(("failed", "rejected")),
            UpiMandate.created_at >= start,
            UpiMandate.created_at < end,
        )
        .scalar()
        or 0
    )


def _recommended_action(anomaly_type: str) -> str:
    mapping = {
        "upi_failure_spike": "Check UPI PSP status and rerun retries within cooldown limits.",
        "card_failure_spike": "Review card network provider status and failure codes in the payment stream.",
        "payment_failure_spike": "Investigate the merchant payment flow and provider error mix.",
        "provider_timeout_increase": "Escalate to the payment provider and reduce timeout-based retry pressure.",
        "checkout_conversion_drop": "A/B test checkout steps and surface retry/help prompts at high drop-off stages.",
        "mandate_failure_spike": "Verify mandate registration flow and notify affected customers.",
        "unusual_retry_rate": "Enforce retry cooldowns and cap attempts to protect the provider.",
    }
    return mapping.get(anomaly_type, "Investigate the anomaly and review affected transactions.")