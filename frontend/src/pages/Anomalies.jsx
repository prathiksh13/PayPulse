import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Siren, RefreshCw, ArrowUpRight } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getAnomalies } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { navigate } from '../hooks/useHashRoute';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { Select, Field } from '../components/ui/Field';
import { SeverityBadge } from '../components/ui/StatusBadge';
import { AnomalyDrawer } from '../components/anomalies/AnomalyDrawer';
import { ANOMALY_TYPE, SEVERITY_ORDER } from '../types';
import { fmtNum, fmtDateTime, titleCase } from '../utils/format';

export function Anomalies() {
  const { dateRange } = useApp();
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [viewing, setViewing] = useState(null);

  const api = useApi(() => getAnomalies({ from: dateRange.from, to: dateRange.to, status: statusFilter || undefined, severity: severityFilter || undefined }), [dateRange, statusFilter, severityFilter]);

  const rows = api.data?.items || api.data?.anomalies || (Array.isArray(api.data) ? api.data : []);

  const counts = useMemo(() => {
    const out = { total: rows.length, critical: 0, high: 0, medium: 0 };
    rows.forEach((a) => {
      const severity = String(a.severity || '').toLowerCase();
      if (severity === 'critical') out.critical += 1;
      if (severity === 'high') out.high += 1;
      if (severity === 'medium') out.medium += 1;
    });
    return out;
  }, [rows]);

  const anomalyName = (a) => ANOMALY_TYPE[(a.type || '').toLowerCase()] || titleCase(a.type || a.anomaly_type || 'Anomaly');

  return (
    <div className="page">
      <section className="stats-grid">
        <StatCard label="Total anomalies" value={api.data ? fmtNum(counts.total) : 'No data available'} sub="detected in selected window" icon={Siren} />
        <StatCard label="Critical severity" value={api.data ? fmtNum(counts.critical) : 'No data available'} sub="needs immediate attention" icon={AlertTriangle} />
        <StatCard label="High severity" value={api.data ? fmtNum(counts.high) : 'No data available'} sub="requires investigation" icon={AlertTriangle} />
        <StatCard label="Medium severity" value={api.data ? fmtNum(counts.medium) : 'No data available'} sub="monitor and investigate" icon={CheckCircle2} />
      </section>

      <Panel
        title="Anomalies"
        subtitle={`${rows.length} anomalies in window · ${dateRange.label}`}
        actions={
          <div className="panel-actions">
            <Field>
              <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="resolved">Resolved</option>
              </Select>
            </Field>
            <Field>
              <Select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
                <option value="">All severities</option>
                {SEVERITY_ORDER.map((s) => (
                  <option key={s} value={s}>{titleCase(s)}</option>
                ))}
              </Select>
            </Field>
            <Button variant="outline" size="sm" onClick={api.refresh}>
              <RefreshCw size={13} /> Refresh
            </Button>
          </div>
        }
      >
        {api.loading ? (
          <WaitingState title="Loading anomalies…" />
        ) : api.networkError ? (
          <ErrorState error={api.error} onRetry={api.refresh} />
        ) : api.unavailable ? (
          <WaitingState title="Insufficient historical data" description={`A reliable baseline is not available for: ${(api.data?.insufficient_data || []).join(', ') || 'the selected window'}.`} />
        ) : rows.length === 0 ? (
          <WaitingState title="No anomalies detected" description="The agent found nothing unusual across your payment flow in this window." />
        ) : (
          <div className="anomaly-list">
            {rows.map((a) => (
              <div className={`anomaly-card sev-${a.severity}`} key={a.id}>
                <div className="anomaly-main">
                  <div className="anomaly-title">
                    <SeverityBadge value={a.severity} />
                    <strong>{a.title || anomalyName(a)}</strong>
                  </div>
                  <p>{a.description || a.likely_cause || 'No description available.'}</p>
                </div>
                <div className="anomaly-metrics">
                  <div><span>Detected</span><strong>{fmtDateTime(a.detected_at || a.detectedAt || a.created_at)}</strong></div>
                  <div><span>{a.metric || 'Current'}</span><strong>{a.current_value != null ? a.current_value : '—'}</strong></div>
                  <div><span>Baseline</span><strong>{a.baseline_value != null ? a.baseline_value : '—'}</strong></div>
                  <div><span>Change</span><strong>{a.change_percent != null ? `${a.change_percent > 0 ? '+' : ''}${a.change_percent}%` : '—'}</strong></div>
                  <div><span>Affected</span><strong>{a.affected_transactions != null ? `${fmtNum(a.affected_transactions)} txns` : '—'}</strong></div>
                </div>
                {a.supporting_data?.length > 0 && <p className="muted">Supporting data: {a.supporting_data.map((item) => JSON.stringify(item)).join(' · ')}</p>}
                <div className="anomaly-actions">
                  <Button size="sm" variant="outline" onClick={() => setViewing(a.id)}>
                    Investigate <ArrowUpRight size={13} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      navigate('/ai-agent');
                      toast('Anomaly handed to AI agent', 'info', { description: anomalyName(a) });
                    }}
                  >
                    Deep dive
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <AnomalyDrawer
        open={!!viewing}
        anomalyId={viewing}
        onClose={() => setViewing(null)}
        onInterrogate={() => {
          setViewing(null);
          navigate('/ai-agent');
        }}
      />
    </div>
  );
}
