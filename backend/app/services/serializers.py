from ..models import Anomaly, Payment, PaymentAttempt, PaymentEvent, RecoveryAction, UpiMandate
from ..utils.helpers import iso, to_float

PAYMENT_STATUS_SUCCEEDED = {"success", "captured", "authorized"}
PAYMENT_STATUS_FAILED = {"failed", "attempted"}
PAYMENT_STATUS_REFUNDED = {"refunded", "partially_refunded"}
PAYMENT_TERMINAL = PAYMENT_STATUS_SUCCEEDED | PAYMENT_STATUS_FAILED


def payment_status_from_rzp(status: str | None) -> str:
    """Map a Razorpay payment status to the frontend vocabulary."""
    s = (status or "pending").lower()
    if s in ("success", "captured"):
        return "captured"
    if s == "authorized":
        return "authorized"
    if s in ("failed", "attempted"):
        return "failed"
    if s == "refunded":
        return "refunded"
    return "pending"


def payment_to_dict(p: Payment, *, with_recovery: RecoveryAction | None = None) -> dict:
    return {
        "id": p.payment_id,
        "payment_id": p.payment_id,
        "order_id": p.order_id,
        "razorpay_order_id": p.rzp_order_id,
        "orderId": p.rzp_order_id or p.order_id,
        "link_id": p.link_id,
        "reference_id": p.link_id,
        "amount": to_float(p.amount),
        "currency": p.currency,
        "method": p.method,
        "status": p.status,
        "failure_code": p.failure_code,
        "failure_reason": p.failure_reason,
        "failureReason": p.failure_reason,
        "customer": {"name": p.customer_name, "email": p.email, "contact": p.contact},
        "customer_name": p.customer_name,
        "email": p.email,
        "contact": p.contact,
        "description": p.description,
        "is_refunded": p.is_refunded,
        "refunded_amount": to_float(p.refunded_amount),
        "attempt_count": p.attempt_count,
        "created_at": iso(p.created_at),
        "createdAt": iso(p.created_at),
        "updated_at": iso(p.updated_at),
    }


def payment_detail_to_dict(
    p: Payment,
    attempts: list[PaymentAttempt],
    events: list[PaymentEvent],
    recovery: RecoveryAction | None,
) -> dict:
    data = payment_to_dict(p)
    data["attempts"] = [
        {
            "attempt_id": a.attempt_id,
            "status": a.status,
            "amount": to_float(a.amount),
            "method": a.method,
            "error_code": a.error_code,
            "failure_reason": a.error_reason,
            "failureReason": a.error_reason,
            "created_at": iso(a.created_at),
            "createdAt": iso(a.created_at),
        }
        for a in attempts
    ]
    data["timeline"] = [
        {
            "title": e.event_type,
            "status": e.status,
            "description": e.error_reason or (e.status or ""),
            "created_at": iso(e.received_at),
            "createdAt": iso(e.received_at),
            "at": iso(e.received_at),
        }
        for e in events
    ]
    if recovery and recovery.status in ("pending", "in_progress", "executed"):
        data["recommended_action"] = recovery.recommended_action or recovery.primary_action
        data["recovery"] = recovery_to_dict(recovery)
    return data


def mandate_to_dict(m: UpiMandate) -> dict:
    return {
        "id": m.mandate_id,
        "mandate_id": m.mandate_id,
        "rzp_mandate_id": m.mandate_id,
        "customer": {"name": m.customer_name, "email": m.customer_email, "contact": m.customer_contact},
        "customer_name": m.customer_name,
        "amount": to_float(m.amount),
        "frequency": m.frequency,
        "status": m.status,
        "failure_reason": m.failure_reason,
        "failureReason": m.failure_reason,
        "next_debit_at": iso(m.next_debit_at),
        "nextDebitAt": iso(m.next_debit_at),
        "created_at": iso(m.created_at),
        "createdAt": iso(m.created_at),
        "updated_at": iso(m.updated_at),
    }


def recovery_to_dict(r: RecoveryAction) -> dict:
    return {
        "id": str(r.id),
        "payment_id": r.payment_id,
        "payment": r.payment_id,
        "recommended_action": r.recommended_action or r.primary_action,
        "primary_action": r.primary_action,
        "action": r.primary_action,
        "reason": r.reason,
        "evidence": r.evidence,
        "recommendation_reason": r.evidence or r.reason,
        "recovery_probability": to_float(r.recovery_probability),
        "probability": to_float(r.recovery_probability),
        "confidence": to_float(r.recovery_probability),
        "expected_impact": to_float(r.expected_impact),
        "impact": to_float(r.expected_impact),
        "risk": r.risk,
        "status": r.status,
        "amount": to_float(r.amount),
        "retry_count": r.retry_count,
        "requires_approval": r.requires_approval,
        "approved_by": r.approved_by,
        "executed_at": iso(r.executed_at),
        "created_at": iso(r.created_at),
        "createdAt": iso(r.created_at),
        "updated_at": iso(r.updated_at),
    }


def anomaly_to_dict(a: Anomaly) -> dict:
    explanation = a.ai_explanation if isinstance(a.ai_explanation, list) else []
    return {
        "id": str(a.id),
        "type": a.anomaly_type,
        "anomaly_type": a.anomaly_type,
        "severity": a.severity,
        "status": a.status,
        "detected_at": iso(a.detected_at),
        "detectedAt": iso(a.detected_at),
        "resolved_at": iso(a.resolved_at),
        "created_at": iso(a.created_at),
        "metric_current": to_float(a.metric_current),
        "metric_baseline": to_float(a.metric_baseline),
        "affected_transactions": a.affected_transactions,
        "affectedTransactions": a.affected_transactions,
        "amount_at_risk": to_float(a.amount_at_risk),
        "amountAtRisk": to_float(a.amount_at_risk),
        "affected_method": a.affected_method,
        "likely_cause": a.likely_cause,
        "likelyCause": a.likely_cause,
        "ai_explanation": explanation,
        "aiExplanation": a.ai_explanation,
        "recommended_action": a.recommended_action,
        "recommendedAction": a.recommended_action,
    }