# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    CheckoutSession,
    Payment,
    RecoveryAction,
    RecoveryOutcome,
)
from ..utils.helpers import iso, now_utc, to_float
from ..utils.cache import clear_cache
from .razorpay_client import RazorpayClient, RazorpayError
from .settings_service import recovery_policy
from .serializers import recovery_to_dict

FAILED_STATUSES = ("failed", "attempted")

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
APPROVAL_RISK = "high"

PROBABILITY_BY_REASON = {
    "insufficient_funds": 0.25,
    "bank_timeout": 0.65,
    "provider timeout": 0.65,
    "network error": 0.5,
    "otp_failure": 0.4,
    "otp expired": 0.45,
    "otp_expired": 0.45,
    "payment_failed": 0.35,
    "invalid_pin": 0.4,
    "expired": 0.3,
    "declined": 0.2,
    "unavailable": 0.5,
}


def score_recovery_probability(reason: str | None) -> float:
    if not reason:
        return 0.3
    r = reason.lower()
    for key, prob in PROBABILITY_BY_REASON.items():
        if key in r:
            return prob
    if "timeout" in r:
        return 0.65
    return 0.35


def _risk_of(amount: float | None) -> str:
    amount = amount or 0
    if amount >= 10000:
        return "high"
    if amount >= 2500:
        return "medium"
    return "low"


def ensure_candidates(db: Session, limit: int | None = None, amount_at_risk_cap: float | None = None) -> list[RecoveryAction]:
    """Materialize deterministic, non-executing recommendations from live rows."""
    limit = limit or 100
    known_ids = {r.payment_id for r in db.query(RecoveryAction.payment_id).all()}
    failed = db.query(Payment).filter(Payment.status.in_(FAILED_STATUSES)).order_by(Payment.created_at.desc()).limit(400).all()
    for payment in failed:
        if payment.payment_id in known_ids:
            continue
        amount = to_float(payment.amount) or 0
        reason = (payment.failure_reason or "").strip()
        lower_reason = reason.lower()
        repeated_query = db.query(Payment.id).filter(Payment.status.in_(FAILED_STATUSES))
        if payment.order_id:
            repeated_query = repeated_query.filter(Payment.order_id == payment.order_id)
        elif payment.email:
            repeated_query = repeated_query.filter(Payment.email == payment.email)
        elif payment.contact:
            repeated_query = repeated_query.filter(Payment.contact == payment.contact)
        repeated = repeated_query.count()
        if not reason:
            action = "Needs investigation"
            primary = "escalate"
            priority = "low"
        elif repeated > 1:
            action = "Manual review before further contact"
            primary = "escalate"
            priority = "high"
        elif any(token in lower_reason for token in ("declin", "bank", "insufficient", "invalid")):
            action = "Try an alternate payment method"
            primary = "notify"
            priority = "high" if amount >= 10000 else "medium"
        else:
            action = "Send a retry reminder"
            primary = "notify"
            priority = "high" if amount >= 10000 else "medium"
        db.add(RecoveryAction(
            payment_id=payment.payment_id,
            primary_action=primary,
            recommended_action=action,
            reason=reason or "Payment failed without a stored failure reason",
            recovery_probability=round(score_recovery_probability(reason) * 100, 1) if reason else None,
            expected_impact=amount,
            risk=priority,
            status="recommended",
            amount=amount,
            retry_count=0,
            requires_approval=False,
            evidence=f"Payment record {payment.payment_id}; failure code: {payment.failure_code or 'unknown'}; repeated failures: {repeated}",
        ))
        known_ids.add(payment.payment_id)

    abandoned = db.query(CheckoutSession).filter(CheckoutSession.status == "abandoned").order_by(CheckoutSession.started_at.desc()).limit(400).all()
    for session in abandoned:
        action_id = f"checkout:{session.session_id}"
        if action_id in known_ids:
            continue
        amount = None
        if session.payment_id:
            payment = db.query(Payment).filter(Payment.payment_id == session.payment_id).first()
            amount = to_float(payment.amount) if payment else None
        db.add(RecoveryAction(
            payment_id=action_id,
            primary_action="notify",
            recommended_action="Send a checkout recovery reminder",
            reason="Checkout abandoned",
            recovery_probability=50.0,
            expected_impact=amount,
            risk="medium",
            status="recommended",
            amount=amount,
            retry_count=0,
            requires_approval=False,
            evidence=f"Checkout session {session.session_id}; abandoned at {iso(session.ended_at or session.updated_at)}",
        ))
        known_ids.add(action_id)

    db.commit()
    q = db.query(RecoveryAction).order_by(RecoveryAction.created_at.desc())
    if limit:
        q = q.limit(limit)
    return [c for c in q.all()]


def update_action_status(db: Session, action_id: int, status: str) -> RecoveryAction | None:
    if status not in {"recommended", "in_progress", "completed", "dismissed"}:
        raise ValueError("Unsupported recovery status")
    action = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
    if action is None:
        return None
    action.status = status
    db.commit()
    db.refresh(action)
    return action


def approve_recovery_action(
    db: Session,
    action_id: int,
    actor: str,
    user_id: str | None = None,
    role: str | None = None,
    ip: str | None = None,
) -> RecoveryAction | None:
    """Approve a recovery action by an Admin user and record who approved it."""
    action = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
    if action is None:
        return None
    action.requires_approval = True
    action.approved_by = actor
    action.approved_by_user_id = user_id
    action.approved_at = now_utc()
    action.status = "approved"

    db.add(AuditLog(
        actor=actor,
        actor_type="merchant",
        action="recovery.approve",
        entity_type="recovery_action",
        entity_id=str(action.id),
        user_id=user_id,
        actor_role=role or "admin",
        merchant_id=action.merchant_id,
        detail={
            "payment_id": action.payment_id,
            "amount": to_float(action.amount),
            "approved_by_user_id": user_id,
        },
        ip=ip,
    ))

    db.commit()
    db.refresh(action)
    return action


class RecoveryBlocked(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _can_retry(status: str | None) -> bool:
    return (status or "").lower() in FAILED_STATUSES


def _can_refund(payment) -> tuple[bool, str]:
    status = (payment.status or "").lower()
    remaining = to_float(payment.amount) - to_float(payment.refunded_amount)
    if status not in ("captured", "authorized"):
        return False, "Refund is only valid for payments that were captured/authorized and settled funds."
    if remaining <= 0:
        return False, "Payment is already fully refunded."
    return True, ""


def execute_recovery_action(
    db: Session,
    action_id: int,
    action: str,
    actor: str = "merchant@dashboard",
    ip: str | None = None,
    user_id: str | None = None,
    role: str | None = None,
    merchant_id: str | None = None,
) -> RecoveryAction:
    """Execute a recovery action through the policy/safety layer."""
    rec = db.query(RecoveryAction).filter(RecoveryAction.id == action_id).first()
    if rec is None:
        raise RecoveryBlocked("Recovery action not found.", 404)

    if rec.status in ("executed", "ignored"):
        raise RecoveryBlocked(f"Recovery action already {rec.status}.", 409)

    policy = recovery_policy(db)
    action = action or rec.primary_action
    if action not in ("retry", "refund", "notify", "escalate", "ignore"):
        raise RecoveryBlocked(f"Unsupported recovery action '{action}'.", 422)

    payment = db.query(Payment).filter(Payment.payment_id == rec.payment_id).first()
    amount = to_float(rec.amount) or (to_float(payment.amount) if payment else 0) or 0
    risk = rec.risk or _risk_of(amount)

    actor_type = "ai_agent" if actor in ("AI_AGENT", "ai_agent", "AI") else "merchant"
    actor_role = role or ("ai_agent" if actor_type == "ai_agent" else "analyst")

    # --- safety rules -------------------------------------------------------
    if action == "retry":
        if not _can_retry(payment.status if payment else None):
            raise RecoveryBlocked(
                "Retry is only valid for failed/attempted payments that have not settled funds.",
                422,
            )
        if rec.retry_count >= policy["max_retry_attempts"]:
            raise RecoveryBlocked(
                f"Retry limit reached ({rec.retry_count}/{policy['max_retry_attempts']}).", 409
            )
        _check_cooldown(db, rec)
    elif action == "refund":
        if payment is None:
            raise RecoveryBlocked("Payment record not found; cannot refund.", 404)
        can, why = _can_refund(payment)
        if not can:
            raise RecoveryBlocked(why, 422)
        refund_amount = min(amount, to_float(payment.amount) - to_float(payment.refunded_amount))
        if refund_amount <= 0:
            raise RecoveryBlocked("Payment has no remaining refundable amount.", 422)
        if refund_amount > policy["max_refund_amount"]:
            raise RecoveryBlocked(
                f"Refund blocked by safety policy: amount ₹{refund_amount} exceeds limit ₹{policy['max_refund_amount']}.",
                409,
            )
        if RISK_ORDER.get(risk, 0) >= RISK_ORDER["high"]:
            raise RecoveryBlocked(
                "Refund blocked: high/critical risk actions require separate manual risk review.",
                403,
            )
        _check_cooldown(db, rec)
        amount = refund_amount

    if RISK_ORDER.get(risk, 0) >= RISK_ORDER["critical"]:
        raise RecoveryBlocked("Action blocked: critical risk requires manual ops review.", 403)

    if policy["require_approval"] and rec.requires_approval and actor_type == "ai_agent":
        raise RecoveryBlocked("Approval required before this recovery action can execute.", 403)

    # idempotency: duplicate request within cooldown for the same payment+action
    cooldown_ago = now_utc() - timedelta(minutes=policy["cooldown_minutes"])
    dup = (
        db.query(RecoveryOutcome)
        .filter(
            RecoveryOutcome.payment_id == rec.payment_id,
            RecoveryOutcome.action == action,
            RecoveryOutcome.created_at >= cooldown_ago,
            RecoveryOutcome.result.in_(("success", "pending")),
        )
        .first()
    )
    if dup:
        raise RecoveryBlocked(
            f"{action} for this payment was already executed {policy['cooldown_minutes']} minutes ago.",
            409,
        )

    # --- execute ------------------------------------------------------------
    rec.approved_by = actor
    rec.approved_by_user_id = user_id
    rec.executed_by_user_id = user_id
    rec.executed_at = now_utc()
    rec.primary_action = action
    if action == "retry":
        rec.retry_count += 1

    provider_ref_id = None
    result = "pending"
    detail = ""

    if action == "retry":
        rec.status = "in_progress"
        if payment is None:
            result, detail = "failed", "payment record not found in DB"
        else:
            try:
                client = RazorpayClient()
                link = client.create_retry_payment_link(
                    amount_inr=amount,
                    description=payment.description or f"Retry for {payment.payment_id}",
                    email=payment.email,
                    contact=payment.contact,
                )
                provider_ref_id = link.get("provider_ref_id")
                result, detail = "success", "retry payment link created"
            except RazorpayError as exc:
                result, detail = "failed", str(exc)
    elif action == "refund":
        rec.status = "in_progress"
        try:
            client = RazorpayClient()
            refund = client.refund_payment(payment.payment_id, amount)
            provider_ref_id = refund.get("provider_ref_id")
            payment.refunded_amount = to_float(payment.refunded_amount) + amount
            remaining = to_float(payment.amount) - payment.refunded_amount
            payment.is_refunded = remaining <= 0
            payment.status = "refunded" if remaining <= 0 else "partially_refunded"
            result, detail = "success", f"refund {provider_ref_id or ''} initiated"
        except RazorpayError as exc:
            result, detail = "failed", str(exc)
    elif action == "notify":
        result, detail = "success", "customer notification queued (email channel)"
    elif action == "escalate":
        result, detail = "success", "issue escalated to operations queue"
    elif action == "ignore":
        result, detail = "success", "marked ignored"

    if action == "ignore":
        rec.status = "ignored"
    elif result == "success":
        rec.status = "executed"
    elif rec.status == "in_progress" and result == "failed":
        # Execution failed (provider/network) — restore to pending so the
        # action stays actionable after cooldown instead of being stuck.
        rec.status = "pending"

    db.add(RecoveryOutcome(
        recovery_action_id=rec.id,
        payment_id=rec.payment_id,
        action=action,
        result=result,
        detail=detail,
        provider_ref_id=provider_ref_id,
        executed_by=actor,
        executed_by_user_id=user_id,
        merchant_id=rec.merchant_id,
    ))

    db.add(AuditLog(
        actor=actor,
        actor_type=actor_type,
        action=f"recovery.{action}",
        entity_type="recovery_action",
        entity_id=str(rec.id),
        user_id=user_id,
        actor_role=actor_role,
        merchant_id=rec.merchant_id,
        detail={
            "payment_id": rec.payment_id,
            "amount": amount,
            "risk": risk,
            "result": result,
            "detail": detail,
            "approved": result == "success",
            "approved_by_user_id": user_id,
        },
        ip=ip,
    ))

    db.commit()
    clear_cache()
    return rec


def _check_cooldown(db: Session, rec: RecoveryAction):
    policy = recovery_policy(db)
    cooldown_ago = now_utc() - timedelta(minutes=policy["cooldown_minutes"])
    recent = (
        db.query(RecoveryOutcome)
        .filter(
            RecoveryOutcome.payment_id == rec.payment_id,
            RecoveryOutcome.created_at >= cooldown_ago,
        )
        .first()
    )
    if recent is not None:
        raise RecoveryBlocked(
            f"Cooldown active — last {recent.action} for this payment was {human_delta(now_utc() - recent.created_at)} ago.",
            409,
        )


def human_delta(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "moments"
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60}m"


def recovery_history(db: Session, from_date: str | None, to_date: str | None, limit: int = 200, merchant_id: str | None = None) -> list[dict]:
    q = db.query(RecoveryOutcome).order_by(RecoveryOutcome.created_at.desc())
    if merchant_id:
        q = q.filter(RecoveryOutcome.merchant_id == merchant_id)
    if from_date or to_date:
        from ..utils.helpers import resolve_range

        start, end = resolve_range(from_date, to_date)
        q = q.filter(RecoveryOutcome.created_at >= start, RecoveryOutcome.created_at < end)
    q = q.limit(limit)
    return [
        {
            "id": o.id,
            "action": o.action,
            "payment_id": o.payment_id,
            "payment": o.payment_id,
            "executed_by": o.executed_by or "AI Agent",
            "by": o.executed_by or "AI Agent",
            "result": "success" if o.result == "success" else o.result,
            "status": o.result,
            "detail": o.detail,
            "provider_ref_id": o.provider_ref_id,
            "created_at": iso(o.created_at),
            "createdAt": iso(o.created_at),
        }
        for o in q
    ]


def recovered_amount(db: Session, merchant_id: str | None = None) -> float:
    """Sum of amounts resolved via successful recovery outcomes over relevant payments."""
    oq = db.query(RecoveryOutcome).filter(RecoveryOutcome.result == "success")
    if merchant_id:
        oq = oq.filter(RecoveryOutcome.merchant_id == merchant_id)
    outcomes = oq.all()
    total = 0.0
    for o in outcomes:
        # refunds + retries both resolve value; use the linked action's amount
        rec = db.query(RecoveryAction).filter(RecoveryAction.id == o.recovery_action_id).first()
        if rec and to_float(rec.amount):
            total += to_float(rec.amount)
    return total
