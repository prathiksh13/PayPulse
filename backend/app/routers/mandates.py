# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..models import MandateEvent, Payment, UpiMandate
from ..services.serializers import mandate_to_dict
from ..utils.helpers import iso, resolve_range

# NOTE: no prefix here — main.py mounts this router at /api/mandates AND
# /api/upi-mandates, so the route paths ('', /{mandate_id}) are the full
# sub-path. A router prefix would double it (e.g. /api/mandates/mandates).
router = APIRouter(tags=["upi-mandates"])


@router.get("")
def list_mandates(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    status: str | None = None,
    query: str | None = None,
    group: str | None = None,
    page: int | None = Query(None, ge=1),
    limit: int | None = Query(None, ge=1, le=500),
):
    start, end = resolve_range(from_date, to_date)
    q = db.query(UpiMandate).filter(UpiMandate.created_at >= start, UpiMandate.created_at < end)

    if query:
        like = f"%{query.lower()}%"
        q = q.filter(
            or_(
                UpiMandate.mandate_id.ilike(like),
                UpiMandate.customer_email.ilike(like),
                UpiMandate.customer_name.ilike(like),
            )
        )

    base_q = q
    if status:
        q = q.filter(UpiMandate.status == status)

    if group == "day":
        bucket = cast(UpiMandate.created_at, Date) if settings.is_postgres else func.date(UpiMandate.created_at)
        grouped = q.with_entities(
            bucket.label("period"),
            UpiMandate.status,
            func.count(UpiMandate.id),
        ).group_by(bucket, UpiMandate.status).order_by(bucket)
        by_day: dict[str, dict] = {}
        for period, mandate_status, count in grouped.all():
            day = iso(period)
            item = by_day.setdefault(day, {
                "date": day,
                "total": 0,
                "active": 0,
                "failed": 0,
                "pending": 0,
                "cancelled": 0,
            })
            normalized = mandate_status if mandate_status in {"active", "failed", "pending", "cancelled"} else "pending"
            item["total"] += count
            item[normalized] += count
        return {"items": list(by_day.values()), "group": "day"}

    total = q.count()
    rows = q.order_by(UpiMandate.created_at.desc()).offset(((page or 1) - 1) * (limit or 100)).limit(limit or 100).all()

    counts = {
        row[0]: row[1]
        for row in base_q.with_entities(UpiMandate.status, func.count(UpiMandate.id))
        .group_by(UpiMandate.status)
        .all()
    }
    return {
        "items": [mandate_to_dict(m) for m in rows],
        "total": total,
        "counts": {
            "total": sum(counts.values()),
            "active": counts.get("active", 0),
            "failed": counts.get("failed", 0),
            "pending": counts.get("pending", 0),
            "cancelled": counts.get("cancelled", 0),
        },
        "page": page or 1,
        "limit": limit or 100,
        "has_more": ((page or 1) * (limit or 100)) < total,
    }


@router.get("/{mandate_id}")
def get_mandate_detail(mandate_id: str, db: Session = Depends(get_db)):
    m = db.query(UpiMandate).filter(UpiMandate.mandate_id == mandate_id).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Mandate not found")
    data = mandate_to_dict(m)

    events = (
        db.query(MandateEvent)
        .filter(MandateEvent.mandate_id == mandate_id)
        .order_by(MandateEvent.received_at.asc())
        .all()
    )
    data["lifecycle"] = [
        {
            "title": e.event_type.replace("_", " ").title(),
            "status": e.status,
            "event": e.event_type,
            "description": e.error_reason or (e.status or ""),
            "created_at": iso(e.received_at),
            "at": iso(e.received_at),
        }
        for e in events
    ]

    debits = (
        db.query(Payment)
        .filter(Payment.rzp_mandate_id == mandate_id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    data["debit_attempts"] = [debit_to_dict(p) for p in debits]
    data["recommended_action"] = "Monitor mandate health and notify the customer on failure spikes."
    return data


def debit_to_dict(p: Payment) -> dict:
    return {
        "status": "success" if p.status in ("captured", "authorized", "success") else p.status,
        "amount": float(p.amount) if p.amount is not None else None,
        "failure_reason": p.failure_reason,
        "payment_id": p.payment_id,
        "created_at": iso(p.created_at) if p.created_at else None,
    }
