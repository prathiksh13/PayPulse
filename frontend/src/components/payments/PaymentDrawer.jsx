import { useApi } from '../../hooks/useApi';
import { getPayment } from '../../api';
import { Drawer } from '../ui/Drawer';
import { Skeleton } from '../ui/Skeleton';
import { ErrorState } from '../ui/ErrorState';
import { WaitingState } from '../ui/EmptyState';
import { PaymentStatusBadge } from '../ui/StatusBadge';
import { Button } from '../ui/Button';
import { fmtINR, fmtDateTime, titleCase } from '../../utils/format';
import { useToast } from '../../context/ToastContext';

function Row({ label, value }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value ?? '—'}</span>
    </div>
  );
}

export function PaymentDrawer({ open, onClose, paymentId, onRecovery }) {
  const toast = useToast();
  const { data: d, loading, unavailable, networkError, error, refresh } = useApi(
    () => getPayment(paymentId),
    [paymentId],
    { enabled: open && !!paymentId },
  );
  const p = d || {};

  const renderedTitle = p.id ? p.id : paymentId || 'Payment details';

  const showRecoveryAction = () => {
    if (p.recommended_action || p.recovery) {
      onRecovery?.(p);
    } else {
      toast('No recovery recommendation yet', 'info', {
        description: 'The AI agent has not generated a recovery action for this payment.',
      });
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={renderedTitle}
      subtitle={
        <span className="pair-inline">
          {p.status ? <PaymentStatusBadge value={p.status} /> : null}
          {p.amount != null ? <strong className="amount">{fmtINR(p.amount)}</strong> : null}
        </span>
      }
      width={540}
    >
      {loading ? (
        <div className="drawer-skeleton">
          {[100, 88, 70, 95, 80].map((w, i) => (
            <Skeleton key={i} width={`${w}%`} height={14} />
          ))}
        </div>
      ) : networkError ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : unavailable ? (
        <WaitingState
          title="Payment detail unavailable"
          description={`GET /api/payments/${paymentId} is not implemented yet. The timeline, attempts and AI diagnosis will render here once the detail endpoint exists.`}
        />
      ) : (
        <>
          <div className="drawer-section">
            <h4>Transaction</h4>
            <div className="detail-grid">
              <Row label="Order ID" value={p.order_id || p.orderId} />
              <Row label="Amount" value={p.amount != null ? fmtINR(p.amount) : null} />
              <Row label="Method" value={p.method ? titleCase(p.method) : null} />
              <Row label="Currency" value={p.currency} />
              <Row label="Status" value={<PaymentStatusBadge value={p.status} />} />
              <Row label="Failure reason" value={p.failure_reason || p.failureReason} />
            </div>
          </div>

          <div className="drawer-section">
            <h4>Razorpay identifiers</h4>
            <div className="detail-grid">
              <Row label="Payment ID" value={p.id} />
              <Row label="Order ID" value={p.razorpay_order_id || p.order_id || p.orderId} />
              <Row label="Link / reference" value={p.link_id || p.reference_id} />
            </div>
          </div>

          <div className="drawer-section">
            <h4>Customer</h4>
            <div className="detail-grid">
              <Row label="Name" value={p.customer?.name || p.customer_name} />
              <Row label="Email" value={p.customer?.email} />
              <Row label="Contact" value={p.customer?.contact} />
            </div>
          </div>

          {p.attempts && p.attempts.length > 0 ? (
            <div className="drawer-section">
              <h4>Payment attempts</h4>
              <div className="timeline">
                {p.attempts.map((a, i) => (
                  <div className="timeline-item" key={i}>
                    <div className={`timeline-dot ${a.status === 'captured' || a.status === 'success' ? 'ok' : 'bad'}`} />
                    <div className="timeline-copy">
                      <strong>{titleCase(a.status || 'attempt')}</strong>
                      <span>{a.failure_reason || a.failureReason || '—'} · {fmtDateTime(a.created_at || a.createdAt)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {p.timeline && p.timeline.length > 0 ? (
            <div className="drawer-section">
              <h4>Transaction timeline</h4>
              <div className="timeline">
                {p.timeline.map((t, i) => (
                  <div className="timeline-item" key={i}>
                    <div className="timeline-dot" />
                    <div className="timeline-copy">
                      <strong>{t.title || t.status || titleCase(t.event || 'event')}</strong>
                      <span>{t.description || ''} · {fmtDateTime(t.created_at || t.createdAt || t.at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {(p.ai_diagnosis || p.aiDiagnosis) && (
            <div className="drawer-section ai-diagnosis">
              <h4>AI diagnosis</h4>
              <div className="ai-note">
                {(p.ai_diagnosis || p.aiDiagnosis).map((note, i) =>
                  typeof note === 'string' ? <p key={i}>{note}</p> : <p key={i}>{note.text}</p>,
                )}
              </div>
            </div>
          )}

          <div className="drawer-section">
            <h4>Recommended recovery action</h4>
            <div className="reco-box">
              <p>{p.recommended_action || p.recovery?.recommended_action || 'No recovery recommendation generated for this payment yet.'}</p>
              <div className="drawer-actions">
                <Button size="sm" onClick={showRecoveryAction} disabled={!p.recommended_action && !p.recovery}>
                  Open recovery
                </Button>
                <Button size="sm" variant="outline" onClick={() => toast('Payment details synced', 'success')}>
                  Refresh
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </Drawer>
  );
}