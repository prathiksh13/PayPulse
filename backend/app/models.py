from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    rzp_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    link_id: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rzp_mandate_id: Mapped[str | None] = mapped_column(String(64), index=True)

    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    method: Mapped[str | None] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)

    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    customer_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(120), index=True)
    contact: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(String(255))

    is_refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    refunded_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)

    raw: Mapped[dict | None] = mapped_column(JSON)


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(24))
    txn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    method: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_reason: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict | None] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class PaymentAttempt(Base, TimestampMixin):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    txn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(24))
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    method: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_reason: Mapped[str | None] = mapped_column(String(255))


class UpiMandate(Base, TimestampMixin):
    __tablename__ = "upi_mandates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mandate_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    rzp_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), index=True)

    customer_name: Mapped[str | None] = mapped_column(String(120))
    customer_email: Mapped[str | None] = mapped_column(String(120), index=True)
    customer_contact: Mapped[str | None] = mapped_column(String(32))

    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    frequency: Mapped[str | None] = mapped_column(String(24), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    next_debit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    raw: Mapped[dict | None] = mapped_column(JSON)


class MandateEvent(Base):
    __tablename__ = "mandate_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    mandate_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_reason: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict | None] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class CheckoutSession(Base, TimestampMixin):
    __tablename__ = "checkout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    payment_id: Mapped[str | None] = mapped_column(String(64), index=True)
    device: Mapped[str | None] = mapped_column(String(32))
    method: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class CheckoutEvent(Base):
    __tablename__ = "checkout_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    method: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_reason: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Anomaly(Base, TimestampMixin):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_type: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    metric_current: Mapped[float | None] = mapped_column(Float)
    metric_baseline: Mapped[float | None] = mapped_column(Float)
    affected_transactions: Mapped[int | None] = mapped_column(Integer)
    amount_at_risk: Mapped[float | None] = mapped_column(Numeric(14, 2))
    affected_method: Mapped[str | None] = mapped_column(String(32))

    likely_cause: Mapped[str | None] = mapped_column(Text)
    ai_explanation: Mapped[list | None] = mapped_column(JSON)
    recommended_action: Mapped[str | None] = mapped_column(String(160))


class AiDecision(Base):
    __tablename__ = "ai_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(String(24), default="pulseops")
    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[list | None] = mapped_column(JSON)
    stats: Mapped[dict | None] = mapped_column(JSON)
    model: Mapped[str | None] = mapped_column(String(120))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class RecoveryAction(Base, TimestampMixin):
    __tablename__ = "recovery_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    mandate_id: Mapped[str | None] = mapped_column(String(64), index=True)
    primary_action: Mapped[str] = mapped_column(String(24), default="retry")
    recommended_action: Mapped[str | None] = mapped_column(String(96))
    reason: Mapped[str | None] = mapped_column(Text)
    recovery_probability: Mapped[float | None] = mapped_column(Float)
    expected_impact: Mapped[float | None] = mapped_column(Numeric(14, 2))
    risk: Mapped[str] = mapped_column(String(16), default="low")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[str | None] = mapped_column(String(80))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[str | None] = mapped_column(Text)


class RecoveryOutcome(Base):
    __tablename__ = "recovery_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recovery_action_id: Mapped[int] = mapped_column(Integer, index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(24))
    result: Mapped[str] = mapped_column(String(20), default="pending")
    detail: Mapped[str | None] = mapped_column(Text)
    provider_ref_id: Mapped[str | None] = mapped_column(String(120))
    executed_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(120))
    actor_type: Mapped[str] = mapped_column(String(24), default="merchant")
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    detail: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    report_type: Mapped[str] = mapped_column(String(16), default="daily")
    period_from: Mapped[datetime.date] = mapped_column(Date)
    period_to: Mapped[datetime.date] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
