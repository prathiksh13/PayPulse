import { request, qs } from './client';

/**
 * Centralized backend API surface. Every component consumes these —
 * no fetch() calls are scattered through pages.
 *
 * Each function returns a normalized envelope: { ok, status, data | error, network }.
 * A 404 response means the endpoint is not implemented yet on the backend;
 * the UI renders an honest "Waiting for events / No data available" state.
 */

// ---------- Health / connectivity ----------
export const getHealth = () => request('/health');

// ---------- Overview ----------
export const getDashboard = (range = {}) =>
  request(`/dashboard/summary${qs(range)}`);

export const getFailureBreakdown = (range = {}) =>
  request(`/dashboard/failure-breakdown${qs(range)}`);

export const getMethodDistribution = (range = {}) =>
  request(`/dashboard/methods${qs(range)}`);

export const getPaymentTrend = (range = {}) =>
  request(`/dashboard/series${qs({ group: 'day', ...range })}`);

// ---------- Payments ----------
export const getPayments = (filters = {}) =>
  request(`/payments${qs(filters)}`);

export const getPayment = (id) =>
  request(`/payments/${encodeURIComponent(id)}`);

export const refundPayment = (id, payload = {}) =>
  request(`/payments/${encodeURIComponent(id)}/refund`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const getPaymentSeries = (range = {}) =>
  request(`/payments${qs({ group: 'day', ...range })}`);

// ---------- UPI mandates ----------
export const getMandates = (filters = {}) =>
  request(`/mandates${qs(filters)}`);

export const getMandate = (id) =>
  request(`/mandates/${encodeURIComponent(id)}`);

// ---------- Checkout intelligence ----------
export const getCheckoutAnalytics = (range = {}) =>
  request(`/checkout/analytics${qs(range)}`);

export const getCheckoutIntelligenceSummary = (range = {}) =>
  request(`/checkout-intelligence/summary${qs(range)}`);

export const getCheckoutIntelligenceTrend = (range = {}) =>
  request(`/checkout-intelligence/trend${qs(range)}`);

export const getCheckoutIntelligenceDropoffReasons = (range = {}) =>
  request(`/checkout-intelligence/dropoff-reasons${qs(range)}`);

export const getRecentCheckouts = (range = {}) =>
  request(`/checkout-intelligence/recent${qs(range)}`);

// ---------- Test Mode checkout (Razorpay Checkout SDK) ----------
export const createTestPayOrder = (payload) =>
  request('/checkout/order', { method: 'POST', body: JSON.stringify(payload) });

export const verifyTestPayment = (payload) =>
  request('/checkout/verify', { method: 'POST', body: JSON.stringify(payload) });

export const syncTestPayment = (paymentId) =>
  request('/checkout/payment', { method: 'POST', body: JSON.stringify({ payment_id: paymentId }) });

export const reportCheckoutEvent = (event) =>
  request('/webhooks/checkout', { method: 'POST', body: JSON.stringify(event) });

// ---------- Anomalies ----------
export const getAnomalies = (filters = {}) =>
  request(`/anomalies${qs(filters)}`);

export const getAnomaly = (id) =>
  request(`/anomalies/${encodeURIComponent(id)}`);

// ---------- Recovery actions ----------
export const getRecoveryActions = (filters = {}) =>
  request(`/recovery/actions${qs(filters)}`);

export const executeRecoveryAction = (id, action) =>
  request(`/recovery/actions/${encodeURIComponent(id)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  });

export const updateRecoveryActionStatus = (id, status) =>
  request(`/recovery/actions/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });

export const getRecoveryHistory = (range = {}) =>
  request(`/recovery/actions/history${qs(range)}`);

// ---------- Reports ----------
export const getReports = (config = {}) =>
  request(`/reports/summary${qs(config)}`);

// ---------- Settings ----------
export const getSettings = () => request('/settings');
export const updateSettings = (settings) =>
  request('/settings', { method: 'PUT', body: JSON.stringify(settings) });

// ---------- AI Operations Agent ----------
export const getAgentStatus = () => request('/agent/status');
export const getAgentInvestigations = () => request('/agent/investigations');
export const askAgent = (payload) =>
  request('/agent/ask', { method: 'POST', body: JSON.stringify(payload) });

export const analyzeAgent = (payload) =>
  request('/ai-agent/analyze', { method: 'POST', body: JSON.stringify(payload) });

// ---------- Notifications ----------
export const getNotifications = () => request('/notifications');

// ---------- Cache ----------
export const invalidateCache = () =>
  request('/cache/invalidate', { method: 'POST', body: '{}' });
