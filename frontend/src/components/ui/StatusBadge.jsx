import { PAYMENT_STATUS, MANDATE_STATUS, SEVERITY, RECOVERY_STATUS } from '../../types';
import { titleCase } from '../../utils/format';
import { Badge } from './Badge';

export function StatusBadge({ value, meta = PAYMENT_STATUS, label }) {
  if (!value) return <span className="muted">—</span>;
  const normalized = String(value).toLowerCase();
  const entry = meta[normalized] || meta[label];
  const tone = entry?.tone || 'muted';
  const text = entry?.label || label || titleCase(value);
  return <Badge tone={tone}>{text}</Badge>;
}

export function PaymentStatusBadge({ value }) {
  return <StatusBadge value={value} meta={PAYMENT_STATUS} />;
}

export function MandateStatusBadge({ value }) {
  return <StatusBadge value={value} meta={MANDATE_STATUS} />;
}

export function SeverityBadge({ value }) {
  return <StatusBadge value={value} meta={SEVERITY} />;
}

export function RecoveryStatusBadge({ value }) {
  return <StatusBadge value={value} meta={RECOVERY_STATUS} />;
}