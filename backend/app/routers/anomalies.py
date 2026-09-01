from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Anomaly
from ..routers.auth import CurrentUser, get_current_user
from ..services.anomalies import detect_with_status, resolve_anomaly
from ..services.analytics import SUPPORTED_ANOMALY_TYPES
from ..services.serializers import anomaly_to_dict
from ..utils.helpers import resolve_range

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("")
def list_anomalies(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    status: str | None = None,
    severity: str | None = None,
    page: int | None = Query(None, ge=1),
    limit: int | None = Query(None, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
):
    start, end = resolve_range(from_date, to_date)

    try:
        # Detection runs against real payment and checkout statistics only.
        _, insufficient = detect_with_status(db, from_date, to_date)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Anomaly detection data is temporarily unavailable") from exc

    q = db.query(Anomaly).filter(Anomaly.anomaly_type.in_(SUPPORTED_ANOMALY_TYPES), Anomaly.detected_at >= start, Anomaly.detected_at < end)
    if current_user.merchant_id:
        q = q.filter(Anomaly.merchant_id == current_user.merchant_id)
    if status:
        q = q.filter(Anomaly.status == status)
    if severity:
        q = q.filter(Anomaly.severity == severity)

    total = q.count()
    rows = q.order_by(Anomaly.detected_at.desc()).offset(((page or 1) - 1) * (limit or 100)).limit(limit or 100).all()
    return {
        "items": [anomaly_to_dict(a) for a in rows],
        "total": total,
        "page": page or 1,
        "limit": limit or 100,
        "has_more": ((page or 1) * (limit or 100)) < total,
        "insufficient_data": insufficient,
    }


@router.get("/{anomaly_id}")
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    a = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if a is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly_to_dict(a)


@router.post("/{anomaly_id}/resolve")
def mark_resolved(anomaly_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    a = resolve_anomaly(db, anomaly_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly_to_dict(a)
