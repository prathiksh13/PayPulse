from __future__ import annotations

import json
import time
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

from ..models import AiDecision, AuditLog, Payment, RecoveryAction
from ..utils.helpers import now_utc, to_float
from . import ai_agent
from .anomalies import detect_and_store
from .recovery_engine import ensure_candidates

FAILED_STATUSES = ("failed", "attempted")
RECENT_WINDOW_MINUTES = 15
GROQ_TIMEOUT = 20.0

SUPPORTED_ACTION_TEXT = {
    "retry": "Retry eligible payment",
    "notify": "Notify customer and suggest another payment method",
    "suggest_other_method": "Suggest another payment method",
    "refund": "Refund — requires approval",
    "escalate": "Escalate to operations",
}


class PipelineNotRun(Exception):
    pass


def analyze_failures() -> dict:
    """Entry point for the automatic foreground/failure pipeline. Opens its own
    session so it can run in a BackgroundTask without a request session."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        return _analyze(db)
    except Exception as exc:  # noqa: BLE001 — never crash the request that scheduled us
        try:
            db.rollback()
            db.add(AuditLog(
                actor="ai_agent",
                actor_type="ai_agent",
                action="ai.failure_analysis.error",
                entity_type="pipeline",
                entity_id="pipeline",
                detail={"error": str(exc)},
            ))
            db.commit()
        except Exception:  # noqa: BLE001
            pass
        return {"triggered": False, "error": str(exc)}
    finally:
        db.close()


def _analyze(db: Session) -> dict:
    started = time.monotonic()

    # 1. Repeated-failure/anomaly detection from real DB stats (once/day/type).
    anomalies = detect_and_store(db)

    # 2. New failed payments (not yet turned into a recovery opportunity).
    cutoff = now_utc() - timedelta(minutes=RECENT_WINDOW_MINUTES)
    covered = {
        r.payment_id
        for r in db.query(RecoveryAction).filter(
            RecoveryAction.status.in_(("pending", "in_progress"))
        ).all()
    }
    failed_rows = (
        db.query(Payment)
        .filter(
            Payment.status.in_(FAILED_STATUSES),
            Payment.created_at >= cutoff,
        )
        .order_by(Payment.created_at.desc())
        .limit(20)
        .all()
    )
    new_failures = [p for p in failed_rows if p.payment_id not in covered]
    if not new_failures and not anomalies:
        return {
            "triggered": False,
            "failures_analyzed": 0,
            "anomalies": len(anomalies),
            "source": None,
        }

    # 3. Build the failure context for the LLM.
    failures = [
        {
            "payment_id": p.payment_id,
            "order_id": p.order_id,
            "amount_inr": to_float(p.amount) or 0,
            "method": p.method,
            "failure_code": p.failure_code,
            "failure_reason": p.failure_reason,
            "attempt_count": p.attempt_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in new_failures
    ]
    anomaly_summary = [
        {
            "type": a.anomaly_type,
            "severity": a.severity,
            "current": a.metric_current,
            "baseline": a.metric_baseline,
            "affected_transactions": a.affected_transactions,
            "amount_at_risk": to_float(a.amount_at_risk) or 0,
        }
        for a in anomalies
    ]

    # 4. Get root cause + categorization + safe recommendation from Groq
    #    (deterministic classifier as a hard fallback — never blocks on the LLM).
    if ai_agent.settings.groq_configured and failures:
        try:
            classification = _classify_with_groq(failures, anomaly_summary)
            source = "groq"
        except (ai_agent.GroqUnavailable, ValueError):
            classification = _classify_deterministic(failures)
            source = "deterministic-fallback"
    else:
        classification = _classify_deterministic(failures)
        source = "deterministic" if not ai_agent.settings.groq_configured else "deterministic-fallback"

    # 5. Persist the AI insight onto today's anomalies.
    _annotate_anomalies(db, anomalies, classification, source)

    # 6. Materialize recovery opportunities (existing engine) then enrich the
    #    newly created ones with the AI recommendation.
    ensure_candidates(db)
    analyzed_ids = [p.payment_id for p in new_failures]
    if analyzed_ids:
        _enrich_recovery_actions(db, analyzed_ids, classification)

    # 7. Store the investigation row.
    answer = _format_answer(classification, failures, anomalies, source)
    latency_ms = int((time.monotonic() - started) * 1000)
    db.add(AiDecision(
        question=f"Root cause analysis for {len(failures)} recent failed payment(s)" if failures
        else "Anomaly investigation from live payment statistics",
        answer=answer,
        tool_calls=[
            {"name": "get_failed_payments", "status": "executed"},
            {"name": "get_anomalies", "status": "executed"},
            {"name": "classify_failure", "status": "executed", "source": source},
        ],
        stats={
            "failures_analyzed": len(failures),
            "payment_ids": analyzed_ids,
            "anomalies": anomaly_summary,
            "amount_at_risk": sum(f["amount_inr"] for f in failures),
            "classification": classification.get("summary"),
        },
        model=ai_agent.settings.groq_model if source.startswith("groq") else source,
        latency_ms=latency_ms,
    ))

    db.add(AuditLog(
        actor="ai_agent",
        actor_type="ai_agent",
        action="ai.failure_analysis",
        entity_type="pipeline",
        entity_id="failure-analysis",
        detail={
            "failures_analyzed": len(failures),
            "payment_ids": analyzed_ids,
            "anomalies": [a.anomaly_type for a in anomalies],
            "source": source,
            "recommended_actions": [f["recommended_action"] for f in failures],
        },
    ))
    db.commit()

    return {
        "triggered": True,
        "failures_analyzed": len(failures),
        "anomalies": len(anomalies),
        "source": source,
        "payment_ids": analyzed_ids,
    }


def _annotate_anomalies(db: Session, anomalies: list, classification: dict, source: str) -> None:
    summary = classification.get("summary") or {}
    root = summary.get("root_cause")
    rec = summary.get("recommended_action")
    for a in anomalies:
        if a.status != "active":
            continue
        insights = [
            f"AI analysis ({source}): {root or a.likely_cause}",
        ]
        if rec:
            insights.append(f"Recommended action: {rec}")
        if summary.get("explanation"):
            insights.append(summary["explanation"])
        a.ai_explanation = (a.ai_explanation or []) + insights
        if root:
            a.likely_cause = root
        a.recommended_action = summary.get("recommended_action") or a.recommended_action


def _enrich_recovery_actions(db: Session, payment_ids: list[str], classification: dict) -> None:
    if not payment_ids:
        return
    action_map = {f["payment_id"]: f for f in classification.get("failures", [])}
    for pid in payment_ids:
        rec = db.query(RecoveryAction).filter(
            RecoveryAction.payment_id == pid,
            RecoveryAction.status.in_(("pending", "in_progress")),
        ).order_by(RecoveryAction.created_at.desc()).first()
        if rec is None:
            continue
        info = action_map.get(pid) or {}
        action_code = info.get("recommended_action") or rec.primary_action
        primary = _supportable(action_code)
        rec.primary_action = primary
        rec.recommended_action = SUPPORTED_ACTION_TEXT.get(primary, SUPPORTED_ACTION_TEXT["escalate"])
        if info.get("root_cause"):
            rec.reason = info["root_cause"]
        evidence = rec.evidence or ""
        rec.evidence = (f"AI root cause: {info.get('root_cause') or 'n/a'}; categories: "
                        f"{' / '.join(a.get('type', '') for a in info.get('anomalies', []) or [a])} — {evidence}").strip()
        if info.get("confidence"):
            rec.recovery_probability = round(to_float(info["confidence"]) * 100, 1)
        if info.get("risk"):
            rec.risk = info["risk"]
            rec.requires_approval = info["risk"] in ("high", "critical")
        if info.get("category"):
            rec.reason = f"[{info['category']}] {rec.reason or 'Payment failed'}"


def _supportable(action: str) -> str:
    action = (action or "retry").lower().replace("-", "_").replace(" ", "_")
    if action in ("retry", "refund", "escalate", "ignore", "notify"):
        return action
    if action in ("suggest_other_method", "suggest_another_method", "card_declined", "declined", "invalid_instrument"):
        return "notify"
    return "retry"


def _classify_with_groq(failures: list[dict], anomaly_summary: list[dict]) -> dict:
    system = (
        "You are the PulseOps payment operations AI. Analyze Razorpay (India) payment failures "
        "and return ONLY valid JSON with this exact schema:\n"
        '{"summary": {"category": string, "root_cause": string, "recommended_action": string, '
        '"risk": "low"|"medium"|"high"|"critical", "confidence": number 0..1, "explanation": string}, '
        '"failures": [{"payment_id": string, "category": string, "root_cause": string, '
        '"recommended_action": "retry"|"suggest_other_method"|"refund"|"notify"|"escalate", '
        '"risk": "low"|"medium"|"high", "confidence": number 0..1}]}\n'
        "Recommended actions must be safe: prefer retry for transient/timeout/OTP failures, "
        "suggest another method for card declines, refund only for clearly eligible amounts, "
        "escalate for anything ambiguous. Be concise and specific."
    )
    user = (
        "Analyze these recent failed Razorpay payments:\n"
        + json.dumps(failures, indent=2)
        + "\n\nDetected anomalies:\n"
        + json.dumps(anomaly_summary, indent=2)
    )
    body = {
        "model": ai_agent.settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = httpx.post(
            f"{ai_agent.settings.groq_api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {ai_agent.settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=GROQ_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ai_agent.GroqUnavailable(f"Groq classification failed: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Groq returned a non-object classification")
    summary = data.get("summary") or {}
    failures_out = data.get("failures") or []
    if not isinstance(summary, dict):
        raise ValueError("Groq summary is not an object")
    per_failure = {f.get("payment_id"): f for f in failures_out if isinstance(f, dict)}
    return {"summary": summary, "failures": failures, "per_failure": per_failure}


def _classify_deterministic(failures: list[dict]) -> dict:
    """Rule-based fallback so the pipeline never depends on the LLM being up."""
    by_id: dict[str, dict] = {}
    for f in failures:
        cls = _deterministic_one(f)
        by_id[f["payment_id"]] = cls
        f["category"] = cls["category"]
        f["root_cause"] = cls["root_cause"]
        f["recommended_action"] = cls["recommended_action"]
        f["risk"] = cls["risk"]
        f["confidence"] = cls["confidence"]
    return {
        "summary": _summary_from(by_id),
        "failures": failures,
        "per_failure": by_id,
    }


def _deterministic_one(f: dict) -> dict:
    reason = (f.get("failure_reason") or "").lower()
    code = (f.get("failure_code") or "").lower()
    amount = to_float(f.get("amount_inr")) or 0

    risk = "high" if amount >= 10000 else ("medium" if amount >= 2500 else "low")

    if any(k in reason for k in ("insufficient", "no funds", "no_funds", "low balance")):
        return {"category": "insufficient_funds", "root_cause": "Customer bank account lacks sufficient balance.",
                "recommended_action": "notify", "risk": "low", "confidence": 0.9}
    if any(k in reason for k in ("timeout", "bank_timeout", "provider", "unavailable", "network")):
        return {"category": "transient_provider", "root_cause": "Transient bank/provider timeout or network interruption.",
                "recommended_action": "retry", "risk": risk if risk == "high" else "medium", "confidence": 0.8}
    if any(k in reason for k in ("otp", "otp_expired", "expired otp")):
        return {"category": "otp_verification", "root_cause": "OTP not entered, entered late, or expired before confirmation.",
                "recommended_action": "retry", "risk": "low", "confidence": 0.8}
    if any(k in reason for k in ("declined", "do not honour", "invalid card", "card", "failed to authenticate", "authentication failed", "cancelled by customer")):
        return {"category": "card_declined", "root_cause": "Issuing bank declined the card or authentication failed.",
                "recommended_action": "suggest_other_method", "risk": "low", "confidence": 0.85}
    if any(k in reason for k in ("pin", "invalid pin")):
        return {"category": "customer_error", "root_cause": "Wrong PIN or customer input errors during authentication.",
                "recommended_action": "notify", "risk": "low", "confidence": 0.8}
    if any(k in reason for k in ("expired", "invalid", "expired card")):
        return {"category": "invalid_instrument", "root_cause": "Card/Payment instrument expired or invalid.",
                "recommended_action": "suggest_other_method", "risk": "low", "confidence": 0.85}
    code_hint = code or ""
    if "refused" in code_hint or "declined" in code_hint:
        return {"category": "card_declined", "root_cause": "Minor card declines (issuer refusal).",
                "recommended_action": "suggest_other_method", "risk": "low", "confidence": 0.7}
    return {"category": "unclassified", "root_cause": "Failure reason not clearly categorized from the event data.",
            "recommended_action": "retry", "risk": risk, "confidence": 0.55}


def _summary_from(by_id: dict[str, dict]) -> dict:
    if not by_id:
        return {"category": "none", "root_cause": "No new failed payments in the recent window.",
                "recommended_action": None, "risk": None, "confidence": None, "explanation": ""}
    counts: dict[str, int] = {}
    for c in by_id.values():
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    top_category = max(counts, key=counts.get)
    sample = by_id.get(next(iter(by_id)))
    return {
        "category": top_category,
        "root_cause": sample["root_cause"],
        "recommended_action": sample["recommended_action"],
        "risk": max((c["risk"] for c in by_id.values()), key=lambda r: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(r, 0)),
        "confidence": round(sum(c["confidence"] for c in by_id.values()) / len(by_id), 2),
        "explanation": f"{len(by_id)} payments classified; dominant category: {top_category}.",
    }


def _format_answer(classification: dict, failures: list[dict], anomalies: list, source: str) -> str:
    summary = classification.get("summary") or {}
    lines = [
        f"Root cause ({source}): {summary.get('root_cause') or '—'}",
        f"Category: {summary.get('category')} · Recommended: {summary.get('recommended_action')} · "
        f"Risk: {summary.get('risk')} · Confidence: {summary.get('confidence')}",
    ]
    for f in failures:
        info = classification.get("per_failure", {}).get(f["payment_id"]) or {}
        lines.append(
            f"  • {f['payment_id']} (₹{f['amount_inr']}, {f['method']}): "
            f"{info.get('root_cause') or f.get('failure_reason') or 'no reason'} → {info.get('recommended_action') or 'retry'}"
        )
    if anomalies:
        lines.append(
            "Anomalies: " + "; ".join(
                f"{a.anomaly_type} ({a.severity}, {a.affected_transactions}x)" for a in anomalies
            )
        )
    return "\n".join(lines)