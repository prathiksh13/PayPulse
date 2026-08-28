import { useApi } from '../../hooks/useApi';
import { getMandate } from '../../api';
import { Drawer } from '../ui/Drawer';
import { Skeleton } from '../ui/Skeleton';
import { ErrorState } from '../ui/ErrorState';
import { WaitingState } from '../ui/EmptyState';
import { MandateStatusBadge } from '../ui/StatusBadge';
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

export function MandateDrawer({ open, onClose, mandateId }) {
  const toast = useToast();
  const { data: d, loading, unavailable, networkError, error, refresh } = useApi(
    () => getMandate(mandateId),
    [mandateId],
    { enabled: open && !!mandateId },
  );
  const m = d || {};

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={m.id || mandateId || 'Mandate details'}
      subtitle={m.status ? <MandateStatusBadge value={m.status} /> : null}
      width={540}
    >
      {loading ? (
        <div className="drawer-skeleton">
          {[100, 90, 74, 96].map((w, i) => (
            <Skeleton key={i} width={`${w}%`} height={14} />
          ))}
        </div>
      ) : networkError ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : unavailable ? (
        <WaitingState
          title="Mandate detail unavailable"
          description={`GET /api/mandates/${mandateId} is not implemented yet. Lifecycle, debit attempts and AI diagnosis will render here once the endpoint exists.`}
        />
      ) : (
        <>
          <div className="drawer-section">
            <h4>Mandate</h4>
            <div className="detail-grid">
              <Row label="Customer" value={m.customer?.name || m.customer_name} />
              <Row label="Amount" value={m.amount != null ? fmtINR(m.amount) : null} />
              <Row label="Frequency" value={m.frequency ? titleCase(m.frequency) : null} />
              <Row label="Status" value={<MandateStatusBadge value={m.status} />} />
              <Row label="Failure reason" value={m.failure_reason || m.failureReason} />
              <Row label="Next debit" value={fmtDateTime(m.next_debit_at || m.nextDebitAt)} />
              <Row label="Created" value={fmtDateTime(m.created_at || m.createdAt)} />
            </div>
          </div>

          {m.lifecycle && m.lifecycle.length > 0 ? (
            <div className="drawer-section">
              <h4>Mandate lifecycle</h4>
              <div className="timeline">
                {m.lifecycle.map((t, i) => (
                  <div className="timeline-item" key={i}>
                    <div className={`timeline-dot ${t.status === 'active' || t.success ? 'ok' : t.status === 'failed' ? 'bad' : ''}`} />
                    <div className="timeline-copy">
                      <strong>{t.title || t.status || titleCase(t.event || 'event')}</strong>
                      <span>{t.description || ''} · {fmtDateTime(t.created_at || t.createdAt || t.at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {m.debit_attempts && m.debit_attempts.length > 0 ? (
            <div className="drawer-section">
              <h4>Debit attempts</h4>
              <div className="timeline">
                {m.debit_attempts.map((a, i) => (
                  <div className="timeline-item" key={i}>
                    <div className={`timeline-dot ${a.status === 'success' ? 'ok' : 'bad'}`} />
                    <div className="timeline-copy">
                      <strong>{titleCase(a.status)}</strong>
                      <span>
                        {a.failure_reason || a.failureReason || '—'} · {a.amount != null ? fmtINR(a.amount) : ''} · {fmtDateTime(a.created_at || a.createdAt || a.at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {(m.ai_diagnosis || m.aiDiagnosis) && (
            <div className="drawer-section ai-diagnosis">
              <h4>AI diagnosis</h4>
              <div className="ai-note">
                {(m.ai_diagnosis || m.aiDiagnosis).map((note, i) =>
                  typeof note === 'string' ? <p key={i}>{note}</p> : <p key={i}>{note.text}</p>,
                )}
              </div>
            </div>
          )}

          <div className="drawer-section">
            <h4>Recommended next action</h4>
            <div className="reco-box">
              <p>{m.recommended_action || m.recommendedAction || 'No recommendation generated for this mandate yet.'}</p>
              <div className="drawer-actions">
                <Button size="sm" onClick={() => toast('Recommendation noted', 'info', { description: 'Recovery for mandates will be available once the backend is wired.' })}>
                  Plan recovery
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </Drawer>
  );
}