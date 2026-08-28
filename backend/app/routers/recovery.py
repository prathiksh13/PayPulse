from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RecoveryAction, RecoveryOutcome
from ..services.recovery_engine import (
    RecoveryBlocked,
    ensure_candidates,
    execute_recovery_action,
    recovery_history,
)
from ..services.serializers import recovery_to_dict

router = APIRouter(prefix="/recovery", tags=["recovery"])


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
    return {
        "items": [recovery_to_dict(r) for r in rows],
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
                "created_at": o.created_at.isoformat(),
            }
            for o in rows
        ]
    }