# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time

import httpx

from ..config import settings
from ..models import AiDecision, Payment, RecoveryAction
from ..utils.helpers import iso, to_float
from . import analytics as analytics_svc
from .anomalies import (
    MIN_TRANSACTIONS,
    detect_and_store,
)
from .recovery_engine import ensure_candidates, score_recovery_probability
from .serializers import anomaly_to_dict

GROQ_TIMEOUT = 20.0


class GroqUnavailable(Exception):
    """Raised when the Groq/LLM endpoint is unreachable, times out, or errors.
    Callers must degrade to the deterministic answer instead of failing."""


TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_payment_metrics",
            "description": "Overall payment KPIs: volume, transactions, success rate, failures, amount at risk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "description": "YYYY-MM-DD"},
                    "to": {"type": "string", "description": "YYYY-MM-DD"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_failed_payments",
            "description": "List of failed payments with amount, method and failure reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_failure_breakdown",
            "description": "Top failure reasons grouped by code/reason with counts and amounts.",
            "parameters": {
                "type": "object",
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_checkout_metrics",
            "description": "Checkout funnel conversion, signals, drop-off by method/device and an investigation summary.",
            "parameters": {
                "type": "object",
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_mandate_metrics",
            "description": "UPI mandate totals, active/failed/pending and success rate.",
            "parameters": {
                "type": "object",
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_anomalies",
            "description": "Active anomalies detected from real payment statistics (type, severity, affected count, amount at risk).",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recovery_candidates",
            "description": "AI-ranked recoverable payments with probability, amount and recommended action.",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        },
    },
]


def _exec(ctx: dict, name: str, args: dict) -> dict:
    """Execute a controlled agent tool against live database statistics."""
    db = ctx["db"]
    frm, to = args.get("from"), args.get("to")
    if name == "get_payment_metrics":
        return analytics_svc.compute_summary(db, frm, to)
    if name == "get_failed_payments":
        items = (
            db.query(Payment)
            .filter(Payment.status.in_(("failed", "attempted")))
            .order_by(Payment.created_at.desc())
            .limit(int(args.get("limit", 10)))
            .all()
        )
        return {
            "items": [
                {
                    "id": p.payment_id,
                    "amount": to_float(p.amount),
                    "method": p.method,
                    "status": p.status,
                    "failure_code": p.failure_code,
                    "failure_reason": p.failure_reason,
                    "created_at": iso(p.created_at),
                }
                for p in items
            ],
            "count": len(items),
        }
    if name == "get_failure_breakdown":
        return {"items": analytics_svc.failure_breakdown(db, frm, to)}
    if name == "get_checkout_metrics":
        return analytics_svc.checkout_analytics(db, frm, to)
    if name == "get_mandate_metrics":
        return analytics_svc.mandate_stats(db, frm, to)
    if name == "get_anomalies":
        anomalies = detect_and_store(db, frm, to)
        return {"items": [anomaly_to_dict(a) for a in anomalies[: int(args.get("limit", 10))]]}
    if name == "get_recovery_candidates":
        ensure_candidates(db)
        cands = (
            db.query(RecoveryAction)
            .filter(RecoveryAction.status == "pending")
            .order_by(RecoveryAction.recovery_probability.desc())
            .limit(int(args.get("limit", 10)))
            .all()
        )
        return {
            "items": [
                {
                    "id": c.id,
                    "payment_id": c.payment_id,
                    "amount": to_float(c.amount),
                    "recommended_action": c.primary_action,
                    "probability": to_float(c.recovery_probability),
                }
                for c in cands
            ]
        }
    return {"error": f"unknown tool {name}"}


def _deterministic_answer(db, question: str, from_date, to_date) -> str:
    """Answers common operations questions from real tool outputs without an LLM."""
    q = question.lower()
    failures = db.query(Payment).filter(Payment.status.in_(("failed", "attempted"))).count()
    summary = analytics_svc.compute_summary(db, from_date, to_date)
    breakdown = analytics_svc.failure_breakdown(db, from_date, to_date, limit=5)
    mandates = analytics_svc.mandate_stats(db, from_date, to_date)
    checkout = analytics_svc.checkout_analytics(db, from_date, to_date)
    anomalies = detect_and_store(db, from_date, to_date)

    parts = []
    if any(k in q for k in ("why", "fail", "root", "reason")):
        if failures:
            top = ", ".join(f"{b['reason']} ({b['count']}x" + f")" for b in breakdown[:3])
            parts.append(f"{failures} payments failed. Top causes: {top or 'no stored causes'}.")
            parts.append("Transient failures (timeouts, OTP) are usually retryable; balance/refusal failures need customer action.")
        else:
            parts.append("No failed payments recorded in the window — nothing to diagnose.")
    if any(k in q for k in ("risk", "amount", "revenue", "money")):
        parts.append(
            f"₹{to_float(summary.get('amount_at_risk')) or 0} is at risk across {failures} failed payments "
            f"({summary.get('success_rate')}% success on {summary.get('transactions')} transactions)."
        )
    if any(k in q for k in ("recover", "retry", "refund", "action")):
        ensure_candidates(db)
        cands = (
            db.query(RecoveryAction)
            .filter(RecoveryAction.status == "pending")
            .order_by(RecoveryAction.recovery_probability.desc())
            .limit(5)
            .all()
        )
        parts.append(
            "Recoverable now: " + (", ".join(
                f"{c.payment_id} ({c.primary_action}, ~{to_float(c.recovery_probability) or 0}% likely)"
                for c in cands
            ) if cands else "no recoverable candidates flagged.")
        )
    if any(k in q for k in ("checkout", "drop", "convert", "otp")):
        parts.append(
            f"Checkout: conversion {checkout.get('conversion_rate')}%, {checkout['signals']['otp_completion']}/{checkout['signals']['otp_attempts']} OTP completions, "
            f"{checkout['signals']['payment_retries']} retries. {checkout['investigation']['likely_cause']}"
        )
    if any(k in q for k in ("mandate", "upi")):
        parts.append(
            f"UPI mandates: {mandates['total']} total, {mandates['active']} active, {mandates['failed']} failed "
            f"({mandates.get('success_rate')}% activation)."
        )
    if any(k in q for k in ("anomaly", "alert", "spike", "issue")):
        parts.append(
            f"Active anomalies: {len(anomalies)}. " + "; ".join(
                f"{a.anomaly_type} ({a.severity})" for a in anomalies[:3]
            ) if anomalies else "No active anomalies in the window."
        )
    if not parts:
        combined = {
            "metrics": summary,
            "failure_breakdown": breakdown[:3],
            "checkout_conversion": checkout.get("conversion_rate"),
            "anomalies_active": len(anomalies),
            "failures": failures,
        }
        parts.append("Here are the live payment operations numbers: " + json.dumps(combined, default=str))
    return "\n".join(parts)


def _enrich_investigation(db, checkout: dict) -> dict:
    """Attach a Groq explanation to checkout investigation when possible."""
    # deterministic explanation is already meaningful; leave as-is
    return checkout


def run_agent(db, question: str, from_date: str | None, to_date: str | None) -> dict:
    started = time.monotonic()
    ctx = {"db": db}
    question = (question or "").strip()

    tool_results: list[dict] = []

    if not question:
        return {
            "answer": "Ask about failures, revenue at risk, retries, checkout drop-off and more.",
            "tool_calls": [],
            "model": None,
        }

    if settings.groq_configured:
        try:
            answer, tool_calls = _run_groq_loop(ctx, question, from_date, to_date)
            model_used = settings.groq_model
            source = "groq"
        except GroqUnavailable:
            # Degrade gracefully: never block an operations question on the LLM.
            answer = _deterministic_answer(db, question, from_date, to_date)
            tool_calls = [{"name": "groq", "status": "unavailable-fallback"}]
            model_used = None
            source = "fallback"
    else:
        answer = _deterministic_answer(db, question, from_date, to_date)
        tool_calls = [
            {"name": "get_payment_metrics", "status": "executed"},
            {"name": "get_failure_breakdown", "status": "executed"},
        ]
        model_used = None
        source = "fallback"

    latency_ms = int((time.monotonic() - started) * 1000)
    stats = analytics_svc.compute_summary(db, from_date, to_date)
    db.add(AiDecision(
        question=question,
        answer=answer,
        tool_calls=tool_calls,
        stats=stats,
        model=model_used if model_used else settings.groq_model if settings.groq_configured else "deterministic-fallback",
        latency_ms=latency_ms,
    ))
    db.commit()

    response = {"answer": answer, "tool_calls": tool_calls, "model": "groq" if source == "groq" else "fallback"}
    try:
        response["toolCalls"] = tool_calls
        response["tool_trace"] = tool_results
        response["message"] = {"content": answer}
    except Exception:
        pass
    return response


def _run_groq_loop(ctx: dict, question: str, from_date, to_date) -> tuple[str, list[dict]]:
    system_prompt = (
        "You are the PulseOps AI payment operations agent. Answer ONLY from the tool results. "
        "Do not invent figures. Be concise, operational and specific. "
        "Always state what is at risk and what action the merchant should take. "
        "If a tool returns empty data, say so honestly."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    tool_calls_log: list[dict] = []

    for _round in range(2):
        body = {
            "model": settings.groq_model,
            "messages": messages,
            "tools": TOOL_DEFS,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 700,
        }
        try:
            resp = httpx.post(
                f"{settings.groq_api_base}/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=GROQ_TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise GroqUnavailable(f"Groq request failed: {exc}") from exc
        try:
            message = resp.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as exc:
            raise GroqUnavailable(f"Groq returned an unexpected payload: {exc}") from exc
        messages.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            content = message.get("content") or ""
            return content, tool_calls_log

        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = _exec(ctx, name, args)
                status = "executed"
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
                status = "error"
            tool_calls_log.append({"name": name, "status": status, "args": args})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"tc_{_round}"),
                    "content": json.dumps(result, default=str),
                }
            )

    # loop ended (2 rounds) without a final text — synthesize from tools
    return ("The agent collected live metrics but the model took too many tool rounds. "
            "Review the tool trace for results."), tool_calls_log


def agent_status(db) -> dict:
    from ..models import (
        Anomaly,
        AuditLog,
        Payment,
        RecoveryAction,
        RecoveryOutcome,
    )
    from .recovery_engine import recovered_amount

    active_anomalies = db.query(Anomaly).filter(Anomaly.status == "active").count()
    resolved_anomalies = db.query(Anomaly).filter(Anomaly.status == "resolved").count()
    pending_actions = db.query(RecoveryAction).filter(RecoveryAction.status == "pending").count()
    executed_actions = db.query(RecoveryAction).filter(RecoveryAction.status == "executed").count()
    decisions = db.query(AiDecision).count()
    recovered = recovered_amount(db)
    failures = db.query(Payment).filter(Payment.status.in_(("failed", "attempted"))).count()

    last_decision = db.query(AiDecision).order_by(AiDecision.created_at.desc()).first()
    last_error = (
        db.query(AuditLog)
        .filter(AuditLog.action == "ai.failure_analysis.error")
        .order_by(AuditLog.created_at.desc())
        .first()
    )

    return {
        "enabled": settings.groq_configured,
        "model": settings.groq_model if settings.groq_configured else "deterministic-fallback",
        "groq_configured": settings.groq_configured,
        "issues_detected": active_anomalies + resolved_anomalies,
        "anomalies_active": active_anomalies,
        "investigations": decisions,
        "recommended_actions": pending_actions,
        "actions_executed": executed_actions,
        "recovered_revenue": recovered,
        "failures_in_window": failures,
        "pipeline": {
            "observe": "done",
            "detect": "done" if (active_anomalies or resolved_anomalies) else "waiting",
            "infer": "done" if decisions else "waiting",
            "recommend": "done" if pending_actions else "waiting",
            "approve": "active",
            "execute": "done" if executed_actions else "waiting",
            "learn": "waiting",
            "last_run_at": iso(last_decision.created_at) if last_decision else None,
            "last_source": (last_decision.stats or {}).get("source") if last_decision else None,
            "last_error": (last_error.detail or {}).get("error") if last_error else None,
            "last_error_at": iso(last_error.created_at) if last_error else None,
        },
        "last_active_at": iso(last_decision.created_at) if last_decision else None,
        "updated_at": iso(last_decision.created_at) if last_decision else None,
    }


def investigations(db) -> list[dict]:
    from ..models import Anomaly, AiDecision

    out: list[dict] = []
    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.status == "active")
        .order_by(Anomaly.detected_at.desc())
        .limit(5)
        .all()
    )
    for a in anomalies:
        explanation = a.ai_explanation if isinstance(a.ai_explanation, list) else []
        out.append(
            {
                "id": f"inv-{a.id}",
                "issue": a.likely_cause or a.anomaly_type,
                "type": a.anomaly_type,
                "what_happened": a.likely_cause,
                "started_at": iso(a.detected_at),
                "detected_at": iso(a.detected_at),
                "affected_methods": [a.affected_method] if a.affected_method else [],
                "affected_amount": to_float(a.amount_at_risk) or 0,
                "affected_transactions": a.affected_transactions or 0,
                "root_cause": a.likely_cause,
                "likely_cause": a.likely_cause,
                "confidence": 80 if a.affected_transactions and a.affected_transactions >= MIN_TRANSACTIONS else 60,
                "status": a.status,
                "explanation": explanation,
                "ai_insight": explanation[0] if explanation else None,
                "recommended_action": a.recommended_action,
            }
        )

    recent_decisions = (
        db.query(AiDecision)
        .order_by(AiDecision.created_at.desc())
        .limit(4)
        .all()
    )
    for d in recent_decisions:
        if not d.answer:
            continue
        stats = d.stats or {}
        payment_ids = stats.get("payment_ids") or []
        classification = stats.get("classification") or {}
        out.append(
            {
                "id": f"inv-dec-{d.id}",
                "issue": d.question,
                "type": "ai_investigation",
                "what_happened": d.answer,
                "started_at": iso(d.created_at),
                "detected_at": iso(d.created_at),
                "affected_methods": [],
                "affected_amount": to_float(stats.get("amount_at_risk")) or 0,
                "affected_transactions": stats.get("failures_analyzed") or 0,
                "root_cause": classification.get("root_cause") or d.answer,
                "likely_cause": classification.get("root_cause") or d.answer,
                "confidence": 75,
                "status": "active",
                "recommended_action": classification.get("recommended_action"),
                "pipeline": True,
                "payment_ids": payment_ids[:10],
            }
        )
    return out