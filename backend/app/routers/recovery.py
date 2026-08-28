from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Payment, RecoveryAction, RecoveryOutcome
from ..services.recovery_engine import (
    RecoveryBlocked,
    _can_refund,
    _can_retry,
    ensure_candidates,
    execute_recovery_action,
    recovery_history,
)
from ..services.serializers import recovery_to_dict
from ..utils.helpers import iso

# NOTE: no prefix here — main.py mounts this router at /api/recovery AND
# /api/recovery-actions, so route paths (/actions, /actions/history, ...) must
# be the full sub-path. Using a prefix here would double it (e.g.
# /api/recovery/recovery/actions).
router = APIRouter(tags=["recovery"])


@router.get("/actions")
def list_actions(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    status: str | None = None,
    limit: int = 200,
    page: int | None = Query(None, ge=1),
):
    # Ensure opportunities exist for failed payments (real DB rows only)
    ensure_candidates(db, limit=500)

    q = db.query(RecoveryAction)
    if status:
        q = q.filter(RecoveryAction.status == status)
    if from_date or to_date:
        from ..utils.helpers import resolve_range

        start, end = resolve_range(from_date, to_date)
        q = q.filter(RecoveryAction.created_at >= start, RecoveryAction.created_at < end)

    total = q.count()
    rows = (
        q.order_by(RecoveryAction.recovery_probability.desc(), RecoveryAction.created_at.desc())
        .offset(((page or 1) - 1) * limit)
        .limit(limit)
        .all()
    )
    ids = [r.payment_id for r in rows]
    payments = {
        p.payment_id: p for p in db.query(Payment).filter(Payment.payment_id.in_(ids)).all()
    }
    items = []
    for r in rows:
        data = recovery_to_dict(r)
        p = payments.get(r.payment_id)
        if p:
            data["payment_status"] = p.status
            data["payment_method"] = p.method
            data["payment_amount"] = p.amount
            can_refund, why = _can_refund(p)
            data["can_refund"] = can_refund
            data["refund_blocked_reason"] = why
        else:
            data["payment_status"] = None
            data["can_refund"] = False
            data["refund_blocked_reason"] = "Payment record not found."
        items.append(data)
    return {
        "items": items,
        "total": total,
        "page": page or 1,
        "limit": limit,
        "has_more": ((page or 1) * limit) < total,
    }


@router.get("/actions/history")
def history_endpoint(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int = 200,
):
    items = recovery_history(db, from_date, to_date, limit)
    return {"items": items, "total": len(items), "history": items}


@router.post("/actions/{action_id}/execute")
def execute_action(
    action_id: int,
    body: dict | None = None,
    db: Session = Depends(get_db),
    request: Request = None,
    x_actor: str | None = Header(None, alias="X-Actor"),
):
    action = (body or {}).get("action") if isinstance(body, dict) else None
    actor = x_actor or "merchant@dashboard"
    ip = (request.client.host if request and request.client else None) if request else None
    try:
        rec = execute_recovery_action(db, action_id, action, actor=actor, ip=ip)
    except RecoveryBlocked as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=404, detail="Recovery action not found")
    result = recovery_to_dict(rec)
    payment = db.query(Payment).filter(Payment.payment_id == rec.payment_id).first()
    if payment:
        result["payment_status"] = payment.status
        can_refund, why = _can_refund(payment)
        result["can_refund"] = can_refund
        result["refund_blocked_reason"] = why
    result["approved"] = True
    result["message"] = "Recovery action accepted and routed through the policy/safety layer."
    return {"ok": True, "action": result}


@router.get("/outcomes")
def outcomes(
    db: Session = Depends(get_db),
    payment_id: str | None = None,
    limit: int = 100,
):
    q = db.query(RecoveryOutcome).order_by(RecoveryOutcome.created_at.desc())
    if payment_id:
        q = q.filter(RecoveryOutcome.payment_id == payment_id)
    rows = q.limit(limit).all()
    return {
        "items": [
            {
                "id": o.id,
                "recovery_action_id": o.recovery_action_id,
                "payment_id": o.payment_id,
                "action": o.action,
                "result": o.result,
                "detail": o.detail,
                "provider_ref_id": o.provider_ref_id,
                "executed_by": o.executed_by,
                "created_at": iso(o.created_at),
            }
            for o in rows
        ]
    }