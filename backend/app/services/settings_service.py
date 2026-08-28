from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AppSetting, PaymentEvent
from ..utils.helpers import iso
from .razorpay_client import get_connection_status

DEFAULT_SETTINGS = {
    "merchant": {
        "name": "My Workspace",
        "workspace": "Primary",
        "environment": "Test",
    },
    "ai_agent": {
        "aiEnabled": True,
        "autoRecovery": False,
        "requireApproval": True,
        "maxRetryAttempts": 2,
        "maxRecoveryAmount": 50000,
        "riskThreshold": "medium",
        "recoveryCooldownMinutes": 30,
        "maxRefundAmount": 50000,
    },
    "notifications": {
        "notifyEmail": True,
        "notifyFailureSpike": True,
        "notifyRecovery": True,
        "notifyDailyReport": False,
    },
    "security": {
        "auditLogging": True,
    },
}


def _load_setting(db: Session, key: str) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        return DEFAULT_SETTINGS.get(key, {})
    value = row.value
    if not isinstance(value, dict):
        return DEFAULT_SETTINGS.get(key, {})
    merged = dict(DEFAULT_SETTINGS.get(key, {}))
    merged.update(value)
    return merged


def get_settings(db: Session) -> dict:
    merchant = _load_setting(db, "merchant") or DEFAULT_SETTINGS["merchant"]
    ai_agent = _load_setting(db, "ai_agent") or DEFAULT_SETTINGS["ai_agent"]
    notifications = _load_setting(db, "notifications") or DEFAULT_SETTINGS["notifications"]
    security = _load_setting(db, "security") or DEFAULT_SETTINGS["security"]

    connection = get_connection_status()

    events_count = (
        db.query(PaymentEvent).count()
    )
    last_event = (
        db.query(PaymentEvent).order_by(PaymentEvent.received_at.desc()).first()
    )
    webhook_status = "active" if events_count > 0 else "unconfigured"

    return {
        "merchant": merchant,
        "ai_agent": ai_agent,
        "notifications": notifications,
        "security": security,
        "razorpay": {
            "connection_status": connection["status"],
            "status": connection["status"],
            "environment": connection.get("environment", "test"),
            "mode": connection.get("environment", "test"),
            "api_status": connection.get("api_status"),
            "configured": settings.razorpay_configured,
        },
        "webhook": {
            "status": webhook_status,
            "webhook_status": webhook_status,
            "api_status": connection.get("api_status"),
            "events_received": events_count,
            "last_event_at": iso(last_event.received_at) if last_event else None,
            "secret_configured": settings.webhook_configured,
        },
        "environment": merchant.get("environment", "Test"),
    }


def update_settings(db: Session, payload: dict) -> dict:
    allowed = ("merchant", "ai_agent", "notifications", "security")
    for key in allowed:
        if key in payload and isinstance(payload[key], dict):
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row is None:
                row = AppSetting(key=key, value=payload[key])
                db.add(row)
            else:
                merged = dict(DEFAULT_SETTINGS.get(key, {}))
                merged.update(row.value or {})
                merged.update(payload[key])
                row.value = merged
    db.commit()
    return get_settings(db)


def recovery_policy(db: Session) -> dict:
    ai = _load_setting(db, "ai_agent") or DEFAULT_SETTINGS["ai_agent"]
    return {
        "max_retry_attempts": int(ai.get("maxRetryAttempts", 2)),
        "max_recovery_amount": float(ai.get("maxRecoveryAmount", 50000)),
        "max_refund_amount": float(ai.get("maxRefundAmount", 50000)),
        "risk_threshold": ai.get("riskThreshold", "medium"),
        "cooldown_minutes": int(ai.get("recoveryCooldownMinutes", 30)),
        "require_approval": bool(ai.get("requireApproval", True)),
        "auto_recovery": bool(ai.get("autoRecovery", False)),
    }