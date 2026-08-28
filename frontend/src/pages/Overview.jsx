import {
  CircleDollarSign, CheckCircle2, AlertTriangle, Activity, RefreshCw,
  WalletCards, ArrowUpRight, Store,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getDashboard, getPayments, getRecoveryActions } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { navigate } from '../hooks/useHashRoute';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { DataTable } from '../components/ui/DataTable';
import { PaymentStatusBadge } from '../components/ui/StatusBadge';
import { Button } from '../components/ui/Button';
import { TrendChart } from '../components/charts/TrendChart';
import { BarChartView } from '../components/charts/BarChartView';
import { DonutChart } from '../components/charts/DonutChart';
import { AiInsightWaiting } from '../components/agent/AiInsightCard';
import { fmtCompact, fmtINR, fmtNum, fmtPct, titleCase, timeAgo } from '../utils/format';

export function Overview() {
  const { dateRange } = useApp();
  const toast = useToast();

  const dash = useApi(() => getDashboard({ from: dateRange.from, to: dateRange.to }), [dateRange]);
  const payments = useApi(() => getPayments({ from: dateRange.from, to: dateRange.to, limit: 8 }), [dateRange]);
  const recovery = useApi(() => getRecoveryActions({ status: 'pending', limit: 6 }), [dateRange]);

  const s = dash.data || {};
  const has = dash.data && !dash.loading;
  const txns = payments.data?.items || payments.data?.payments || (Array.isArray(payments.data) ? payments.data : []);
  const opps = recovery.data?.items || recovery.data?.actions || (Array.isArray(recovery.data) ? recovery.data : []);

  const openPayment = (row) => navigate(`/payments?view=${encodeURIComponent(row.id)}`);

  const statCard = (label, value, sub, Icon) => (
    <StatCard
      label={label}
      value={dash.loading ? undefined : has ? value : 'No data available'}
      sub={
        dash.networkError
          ? 'Backend offline'
          : dash.unavailable
            ? 'Waiting for summary API'
            : dash.loading
              ? 'Loading…'
              : sub
      }
      icon={Icon}
      tone="indigo"
    />
  );

  return (
    <div className="page">
      <div className="api-banner row">
        <div>
          <strong>{dash.networkError ? 'Backend unavailable' : dash.unavailable ? 'Endpoints pending' : 'Live backend connected'}</strong>
          <span>
            {dash.networkError
              ? 'Start the FastAPI server on port 8000 — the frontend reads real metrics only from the backend.'
              : dash.unavailable
                ? 'GOT /api/dashboard/summary is live; payment, mandate and checkout endpoints are still pending.'
                : `Summary loaded for ${dateRange.label} from the backend.`}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={() => Promise.all([dash.refresh(), payments.refresh(), recovery.refresh()]).then(() => toast('Dashboard refreshed', 'success'))}>
          <RefreshCw size={13} /> Refresh
        </Button>
      </div>

      <section className="stats-grid">
        {statCard('Total payment volume', fmtCompact(s.volume), `${fmtNum(s.transactions)} transactions`, CircleDollarSign)}
        {statCard('Total transactions', fmtNum(s.transactions), 'live via API', Store)}
        {statCard('Success rate', fmtPct(s.success_rate), 'of all attempts', CheckCircle2)}
        {statCard('Failed payments', fmtNum(s.failed), 'in selected window', AlertTriangle)}
        {statCard('Amount at risk', fmtINR(s.amount_at_risk), 'across failed payments', AlertTriangle)}
        {statCard('Checkout drop-off rate', fmtPct(s.checkout_abandonment), 'vs checkout started', Activity)}
        {statCard('UPI failure rate', 'No data available', 'expect UPI events', WalletCards)}
        {statCard('Recovery rate', 'No data available', 'expect recovery actions', RefreshCw)}
      </section>

      <section className="block">
        {dash.networkError ? (
          <ErrorState error={dash.error} onRetry={dash.refresh} />
        ) : (
          <AiInsightWaiting
            time={`${dateRange.from} → ${dateRange.to}`}
            onInvestigate={() => navigate('/ai-agent')}
          />
        )}
      </section>

      <section className="chart-grid">
        <TrendChart
          title="Payment success / failure trend"
          subtitle="Success and failure rate over time (source: /api/payments)"
          unavailable
        />
        <TrendChart
          title="Payment volume trend"
          subtitle="Processed volume per interval (source: /api/payments?group=day)"
          unavailable
          formatValue={(v) => fmtCompact(v)}
        />
      </section>

      <section className="chart-grid two">
        <BarChartView
          title="Failure reasons"
          subtitle="Distribution of failure codes (source: /api/payments?status=failed)"
          unavailable
          percent
          layout="vertical"
        />
        <DonutChart
          title="Payment method distribution"
          subtitle="Mix of UPI, card and other methods (source: /api/payments)"
          unavailable
        />
      </section>

      <section className="lower-grid">
        <Panel
          title="Recent transactions"
          subtitle={`Latest payment events · ${dateRange.label}`}
          actions={
            <button className="text-btn" onClick={() => navigate('/payments')}>
              View all <ArrowUpRight size={13} />
            </button>
          }
          pad={false}
        >
          {payments.networkError ? (
            <ErrorState error={payments.error} onRetry={payments.refresh} />
          ) : (
            <DataTable
              loading={payments.loading}
              waiting={payments.unavailable}
              onRowClick={openPayment}
              minWidth={760}
              emptyTitle="No payments in this window"
              emptyDescription="Payment events will appear here as the backend ingests Razorpay webhooks."
              columns={[
                { key: 'id', label: 'Payment ID', sortable: true, className: 'mono', render: (r) => r.id || r.payment_id },
                { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
                { key: 'amount', label: 'Amount', sortable: true, className: 'amount', align: 'right', render: (r) => (r.amount != null ? fmtINR(r.amount) : '—') },
                { key: 'method', label: 'Method', sortable: true, render: (r) => (r.method ? titleCase(r.method) : '—') },
                { key: 'status', label: 'Status', sortable: true, render: (r) => <PaymentStatusBadge value={r.status} /> },
                { key: 'failure_reason', label: 'Failure reason', sortable: true, render: (r) => r.failure_reason || r.failureReason || '—' },
                { key: 'created_at', label: 'Timestamp', sortable: true, render: (r) => <span className="muted">{timeAgo(r.created_at || r.createdAt)}</span> },
              ]}
              rows={txns}
            />
          )}
        </Panel>

        <Panel
          title="Recovery opportunities"
          subtitle={`AI-ranked next actions · ${dateRange.label}`}
          actions={
            <button className="text-btn" onClick={() => navigate('/recovery')}>
              Open recovery <ArrowUpRight size={13} />
            </button>
          }
        >
          <div className="metric-hint muted">
            {recovery.networkError
              ? 'Backend offline — recovery opportunities cannot be ranked yet.'
              : recovery.unavailable
                ? 'Recovery opportunities appear here (source: /api/recovery/actions).'
                : `Top opportunities for ${dateRange.label}`}
          </div>
          {!recovery.networkError && !recovery.unavailable && (
            <div className="recovery-list">
              {opps.length === 0 && !recovery.loading ? (
                <WaitingState title="No opportunities right now" description="The AI agent did not flag any recoverable payments in this window." />
              ) : (
                opps.map((o) => (
                  <div className="recovery-item" key={o.id}>
                    <div className="recovery-icon indigo">
                      <RefreshCw size={15} />
                    </div>
                    <div>
                      <strong>{o.recommended_action || 'Recover payment'}</strong>
                      <span>
                        {o.recovery_probability != null ? `${fmtPct(o.recovery_probability)} probability · ` : ''}
                        {o.amount != null ? fmtINR(o.amount) : ''}
                      </span>
                    </div>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => {
                        toast('Recovery review queued', 'info', { description: 'Open the Recovery Actions page to approve and execute.' });
                        navigate('/recovery');
                      }}
                    >
                      Review
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}