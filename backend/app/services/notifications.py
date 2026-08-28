from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Anomaly, RecoveryAction, UpiMandate
from ..utils.helpers import to_float


def build_notifications(db: Session, limit: int = 20) -> list[dict]:
    items: list[dict] = []

    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.status == "active")
        .order_by(Anomaly.detected_at.desc())
        .all()
    )
    for a in anomalies[:5]:
        items.append(
            {
                "id": f"anom-{a.id}",
                "type": "anomaly",
                "title": f"{a.anomaly_type.replace('_', ' ').title()}",
                "message": (
                    f"{a.affected_transactions or 0} affected · ₹{to_float(a.amount_at_risk) or 0} at risk · {a.severity}"
                ),
                "severity": a.severity,
                "read": False,
                "created_at": a.detected_at.isoformat(),
            }
        )

    recoveries = (
        db.query(RecoveryAction)
        .filter(RecoveryAction.status.in_(("pending", "in_progress", "executed")))
        .order_by(RecoveryAction.created_at.desc())
        .all()
    )
    for r in recoveries[:5]:
        items.append(
            {
                "id": f"rec-{r.id}",
                "type": "recovery",
                "title": "Recovery " + (r.status.replace("_", " ")),
                "message": f"{r.payment_id} · {r.primary_action} · ~{to_float(r.recovery_probability) or 0}% likely",
                "read": False,
                "created_at": r.created_at.isoformat(),
            }
        )

    failed_mandates = (
        db.query(UpiMandate)
        .filter(UpiMandate.status.in_(("failed", "rejected")))
        .order_by(UpiMandate.created_at.desc())
        .limit(3)
        .all()
    )
    for m in failed_mandates:
        items.append(
            {
                "id": f"mdt-{m.id}",
                "type": "mandate",
                "title": "Mandate failed",
                "message": f"{m.mandate_id} · {m.failure_reason or 'activation failed'}",
                "read": False,
                "created_at": m.created_at.isoformat(),
            }
        )

    items.sort(key=lambda n: n.get("created_at") or "", reverse=True)
    return items[:limit]