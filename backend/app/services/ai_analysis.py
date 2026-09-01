from __future__ import annotations

import json
import time

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AiDecision, Payment, UpiMandate
from ..utils.helpers import iso, resolve_range, to_float
from . import analytics as analytics_svc
from . import checkout_intelligence


class AnalysisUnavailable(Exception):
    pass


def _context(db: Session, question: str, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> dict:
    q = question.lower()
    general = not any(word in q for word in ("payment", "fail", "checkout", "drop", "mandate", "upi"))
    context: dict = {"period": {"from": from_date, "to": to_date}}

    if general or any(word in q for word in ("payment", "fail", "trend", "today", "attention")):
        start, end = resolve_range(from_date, to_date)
        failures_q = db.query(Payment).filter(
            Payment.status.in_(("failed", "attempted")), Payment.created_at >= start, Payment.created_at < end
        )
        if merchant_id:
            failures_q = failures_q.filter(Payment.merchant_id == merchant_id)
        failures = failures_q.order_by(Payment.created_at.desc()).limit(20).all()
        context["payments"] = {
            "summary": analytics_svc.compute_summary(db, from_date, to_date, merchant_id=merchant_id),
            "failure_breakdown": analytics_svc.failure_breakdown(db, from_date, to_date, limit=8, merchant_id=merchant_id),
            "recent_failures": [
                {
                    "payment_id": p.payment_id,
                    "amount_inr": to_float(p.amount),
                    "method": p.method,
                    "failure_code": p.failure_code,
                    "failure_reason": p.failure_reason,
                    "created_at": iso(p.created_at),
                }
                for p in failures
            ],
        }

    if general or any(word in q for word in ("checkout", "drop", "conversion", "attention")):
        context["checkout"] = {
            "summary": checkout_intelligence.summary(db, from_date, to_date, merchant_id=merchant_id),
            "trend": checkout_intelligence.trend(db, from_date, to_date, merchant_id=merchant_id),
            "dropoff_reasons": checkout_intelligence.dropoff_reasons(db, from_date, to_date, merchant_id=merchant_id),
        }

    if general or any(word in q for word in ("mandate", "upi", "attention")):
        start, end = resolve_range(from_date, to_date)
        mandate_summary = analytics_svc.mandate_stats(db, from_date, to_date, merchant_id=merchant_id)
        failed_q = db.query(UpiMandate).filter(
            UpiMandate.status == "failed",
            UpiMandate.created_at >= start,
            UpiMandate.created_at < end,
        )
        if merchant_id:
            failed_q = failed_q.filter(UpiMandate.merchant_id == merchant_id)
        failed_mandates = failed_q.order_by(UpiMandate.updated_at.desc()).limit(20).all()
        context["mandates"] = {
            "summary": mandate_summary,
            "failed": [
                {
                    "mandate_id": m.mandate_id,
                    "amount": to_float(m.amount),
                    "failure_reason": m.failure_reason,
                    "updated_at": iso(m.updated_at),
                }
                for m in failed_mandates
            ],
        }
    return context


def _insufficient(context: dict) -> bool:
    payments = context.get("payments", {})
    checkout = context.get("checkout", {})
    mandates = context.get("mandates", {})
    return not (
        payments.get("summary", {}).get("transactions")
        or payments.get("recent_failures")
        or checkout.get("summary", {}).get("total_checkout_attempts")
        or mandates.get("summary", {}).get("total")
    )


def _fallback(context: dict, question: str) -> dict:
    if _insufficient(context):
        return {
            "summary": "Insufficient transaction data to identify a reliable pattern.",
            "findings": [],
            "recommendations": [],
            "priority": "low",
            "supporting_data": [],
        }
    findings = []
    recommendations = []
    priority = "low"
    payments = context.get("payments", {})
    payment_summary = payments.get("summary", {})
    failures = payments.get("recent_failures", [])
    if failures:
        top = (payments.get("failure_breakdown") or [{}])[0]
        reason = top.get("reason") or "stored failure reasons"
        count = top.get("count") or len(failures)
        findings.append(f"{len(failures)} failed payment record(s) are present; the leading stored reason is {reason} ({count}).")
        recommendations.append("Review the affected payment method and use existing approval-gated operations for eligible transactions; no action was executed by the agent.")
        priority = "high" if len(failures) >= 3 else "medium"
    checkout = context.get("checkout", {}).get("summary", {})
    if checkout.get("dropped_off_checkouts"):
        findings.append(f"{checkout['dropped_off_checkouts']} checkout attempt(s) were explicitly abandoned or closed before completion.")
        recommendations.append("Investigate the persisted checkout drop-off reasons before changing the checkout flow.")
    mandates = context.get("mandates", {}).get("summary", {})
    if mandates.get("failed"):
        findings.append(f"{mandates['failed']} UPI mandate record(s) are currently failed.")
        recommendations.append("Review the stored mandate failure reason and notify affected customers if appropriate.")
    summary = "Live payment-operations data was reviewed." if findings else "Live data was found, but it does not show a clear operational pattern for this question."
    supporting = failures[:5] + context.get("mandates", {}).get("failed", [])[:5]
    return {"summary": summary, "findings": findings, "recommendations": recommendations, "priority": priority, "supporting_data": supporting}


def _groq(context: dict, question: str) -> dict:
    system = (
        "You are the PayPulse AI Operations Agent. Use ONLY the supplied JSON context. "
        "Never invent IDs, amounts, customers, reasons, counts, or trends. "
        "Return ONLY valid JSON with this schema: "
        '{"summary": string, "findings": [string], "recommendations": [string], '
        '"priority": "low"|"medium"|"high", "supporting_data": [object]}. '
        "Recommendations must be analysis-only: do not execute or claim refunds, retries, cancellations, or other financial actions. "
        "If the context is insufficient, use exactly: Insufficient transaction data to identify a reliable pattern."
    )
    body = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {question}\nLive context:\n{json.dumps(context, default=str)}"},
        ],
        "temperature": 0.0,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            f"{settings.groq_api_base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=20.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
    except httpx.HTTPStatusError as exc:
        raise AnalysisUnavailable(f"Groq rejected the request: {exc.response.text[:300]}") from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise AnalysisUnavailable(str(exc)) from exc
    if not isinstance(result, dict):
        raise AnalysisUnavailable("Groq returned a non-object response")
    result["findings"] = result.get("findings") if isinstance(result.get("findings"), list) else []
    result["recommendations"] = result.get("recommendations") if isinstance(result.get("recommendations"), list) else []
    result["supporting_data"] = result.get("supporting_data") if isinstance(result.get("supporting_data"), list) else []
    result["priority"] = result.get("priority") if result.get("priority") in {"low", "medium", "high"} else "low"
    result["summary"] = str(result.get("summary") or "Insufficient transaction data to identify a reliable pattern.")
    return result


def analyze(db: Session, question: str, from_date: str | None, to_date: str | None, merchant_id: str | None = None) -> dict:
    started = time.monotonic()
    context = _context(db, question, from_date, to_date, merchant_id=merchant_id)
    source = "deterministic-fallback"
    try:
        if _insufficient(context):
            result = _fallback(context, question)
        elif settings.groq_configured:
            result = _groq(context, question)
            source = "groq"
        else:
            result = _fallback(context, question)
    except AnalysisUnavailable:
        result = _fallback(context, question)
    result["source"] = source
    result["question"] = question
    result["model"] = settings.groq_model if source == "groq" else None
    result["latency_ms"] = int((time.monotonic() - started) * 1000)
    db.add(AiDecision(
        question=question,
        answer=result["summary"],
        tool_calls=[{"name": "ai_analysis", "status": "executed", "source": source}],
        stats={"context": context, "priority": result["priority"], "source": source},
        model=result["model"] or "deterministic-fallback",
        latency_ms=result["latency_ms"],
        merchant_id=merchant_id,
    ))
    db.commit()
    return result
