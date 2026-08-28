import { useApi } from '../../hooks/useApi';
import { getAnomaly } from '../../api';
import { Drawer } from '../ui/Drawer';
import { Skeleton } from '../ui/Skeleton';
import { ErrorState } from '../ui/ErrorState';
import { WaitingState } from '../ui/EmptyState';
import { SeverityBadge } from '../ui/StatusBadge';
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

export function AnomalyDrawer({ open, onClose, anomalyId, onInterrogate }) {
  const toast = useToast();
  const { data: d, loading, unavailable, networkError, error, refresh } = useApi(
    () => getAnomaly(anomalyId),
    [anomalyId],
    { enabled: open && !!anomalyId },
  );
  const a = d || {};

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={titleCase(a.type || a.anomaly_type || 'Anomaly')}
      subtitle={a.severity ? <SeverityBadge value={a.severity} /> : null}
      width={540}
    >
      {loading ? (
        <div className="drawer-skeleton">
          {[100, 92, 76, 88].map((w, i) => (
            <Skeleton key={i} width={`${w}%`} height={14} />
          ))}
        </div>
      ) : networkError ? (
        <ErrorState error={error} onRetry={refresh} />
      ) : unavailable ? (
        <WaitingState
          title="Anomaly detail unavailable"
          description={`GET /api/anomalies/${anomalyId} is not implemented yet. The full AI explanation will render here once the endpoint exists.`}
        />
      ) : (
        <>
          <div className="drawer-section">
            <h4>Detection</h4>
            <div className="detail-grid">
              <Row label="Type" value={titleCase(a.type || a.anomaly_type)} />
              <Row label="Severity" value={<SeverityBadge value={a.severity} />} />
              <Row label="Detected" value={fmtDateTime(a.detected_at || a.detectedAt || a.created_at)} />
              <Row label="Status" value={a.status ? titleCase(a.status) : null} />
              <Row label="Affected transactions" value={a.affected_transactions ?? a.affectedTransactions} />
              <Row label="Amount at risk" value={a.amount_at_risk != null ? fmtINR(a.amount_at_risk ?? a.amountAtRisk) : null} />
            </div>
          </div>

          {a.likely_cause || a.likelyCause ? (
            <div className="drawer-section">
              <h4>Likely cause</h4>
              <p className="body-copy">{a.likely_cause || a.likelyCause}</p>
            </div>
          ) : null}

          {(a.ai_explanation || a.aiExplanation) ? (
            <div className="drawer-section ai-diagnosis">
              <h4>AI explanation</h4>
              <div className="ai-note">
                {(a.ai_explanation || a.aiExplanation).map((note, i) => (
                  <p key={i}>{typeof note === 'string' ? note : note.text}</p>
                ))}
              </div>
            </div>
          ) : null}

          {a.recommended_action || a.recommendedAction ? (
            <div className="drawer-section">
              <h4>Recommended action</h4>
              <div className="reco-box">
                <p>{a.recommended_action || a.recommendedAction}</p>
                <div className="drawer-actions">
                  <Button
                    size="sm"
                    onClick={() => {
                      toast('Investigation opened', 'success', { description: 'The AI agent will trace this anomaly across payment events.' });
                      onInterrogate?.(a);
                    }}
                  >
                    Investigate in AI Agent
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </Drawer>
  );
}