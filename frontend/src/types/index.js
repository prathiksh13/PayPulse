/**
 * Shared domain vocabulary: status / method / severity / action metadata.
 *
 * These describe HOW known domain values should be presented — they are not
 * fabricated metrics. Actual numbers always come from the backend API layer.
 */

export const PAYMENT_STATUS = {
  success: { label: 'Success', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  pending: { label: 'Pending', tone: 'warning' },
  refunded: { label: 'Refunded', tone: 'info' },
  partially_refunded: { label: 'Partially refunded', tone: 'info' },
  captured: { label: 'Captured', tone: 'success' },
  authorized: { label: 'Authorized', tone: 'info' },
  attempted: { label: 'Attempted', tone: 'warning' },
  cancelled: { label: 'Cancelled', tone: 'muted' },
};

export const PAYMENT_METHOD = {
  upi: 'UPI',
  card: 'Card',
  netbanking: 'Netbanking',
  wallet: 'Wallet',
  emi: 'EMI',
  mandate: 'Mandate (UPI)',
};

export const MANDATE_STATUS = {
  active: { label: 'Active', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  pending: { label: 'Pending', tone: 'warning' },
  paused: { label: 'Paused', tone: 'info' },
  cancelled: { label: 'Cancelled', tone: 'muted' },
  expired: { label: 'Expired', tone: 'muted' },
};

export const SEVERITY = {
  critical: { label: 'Critical', tone: 'danger' },
  high: { label: 'High', tone: 'warning' },
  medium: { label: 'Medium', tone: 'info' },
  low: { label: 'Low', tone: 'muted' },
};

export const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'];

export const RECOVERY_ACTION_TYPE = {
  retry: { label: 'Retry' },
  refund: { label: 'Refund' },
  notify: { label: 'Notify customer' },
  escalate: { label: 'Escalate' },
  ignore: { label: 'Ignore' },
};

export const RECOVERY_STATUS = {
  pending: { label: 'Pending', tone: 'warning' },
  in_progress: { label: 'In progress', tone: 'info' },
  executed: { label: 'Executed', tone: 'success' },
  reviewed: { label: 'Reviewed', tone: 'info' },
  ignored: { label: 'Ignored', tone: 'muted' },
};

export const ANOMALY_TYPE = {
  upi_failure_spike: 'UPI failure spike',
  card_failure_spike: 'Card failure spike',
  checkout_conversion_drop: 'Checkout conversion drop',
  provider_timeout_increase: 'Provider timeout increase',
  mandate_failure_spike: 'Mandate failure spike',
  unusual_retry_rate: 'Unusual retry rate',
};

export const REPORT_TYPES = [
  { key: 'daily', label: 'Daily payment report', description: 'Volume, success rate and payment health for the period.' },
  { key: 'failure', label: 'Failure report', description: 'Failed transactions grouped by reason, method and amount.' },
  { key: 'recovery', label: 'Recovery report', description: 'Recovered amount, recovery rate and outstanding opportunities.' },
  { key: 'upi', label: 'UPI report', description: 'UPI transaction and mandate health for the period.' },
  { key: 'checkout', label: 'Checkout report', description: 'Checkout funnel, drop-offs and conversion by stage.' },
  { key: 'ai_operations', label: 'AI operations report', description: 'Issues detected, investigations and agent actions taken.' },
];

export const AGENT_PIPELINE = [
  { key: 'observe', label: 'Observe', description: 'Ingesting payment events' },
  { key: 'detect', label: 'Detect', description: 'Spotting anomalies' },
  { key: 'infer', label: 'Infer', description: 'Finding root cause' },
  { key: 'recommend', label: 'Recommend', description: 'Proposing actions' },
  { key: 'approve', label: 'Approve', description: 'Merchant approval' },
  { key: 'execute', label: 'Execute', description: 'Running the action' },
  { key: 'learn', label: 'Learn', description: 'Updating baselines' },
];

export const CHECKOUT_STAGES = [
  'Checkout Started',
  'Payment Method Selected',
  'Payment Initiated',
  'OTP Started',
  'Payment Completed',
];

export const AT_RISK_LABELS = {
  insufficient_funds: 'Insufficient funds',
  bank_timeout: 'Bank / provider timeout',
  otp_failure: 'OTP failure',
  otp_expired: 'OTP expired',
  payment_failed: 'Payment failed',
  unavailable: 'Unavailable',
  invalid_pin: 'Invalid UPI PIN',
  transaction_refused: 'Transaction refused',
  mandate_failed: 'Mandate failed',
  checkout_abandoned: 'Checkout abandoned',
};