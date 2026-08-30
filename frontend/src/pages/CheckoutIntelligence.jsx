import { useMemo } from 'react';
import { CheckCircle2, Clock3, Percent, RefreshCw, ShoppingCart, XCircle } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import {
  getCheckoutIntelligenceDropoffReasons,
  getCheckoutIntelligenceSummary,
  getCheckoutIntelligenceTrend,
  getRecentCheckouts,
} from '../api';
import { useApp } from '../context/AppContext';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { DataTable } from '../components/ui/DataTable';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { BarChartView } from '../components/charts/BarChartView';
import { TrendChart } from '../components/charts/TrendChart';
import { fmtINR, fmtPct, fmtDateTime } from '../utils/format';

export function CheckoutIntelligence() {
  const { dateRange } = useApp();
  const range = { from: dateRange.from, to: dateRange.to };
  const summary = useApi(() => getCheckoutIntelligenceSummary(range), [dateRange]);
  const trend = useApi(() => getCheckoutIntelligenceTrend(range), [dateRange]);
  const reasons = useApi(() => getCheckoutIntelligenceDropoffReasons(range), [dateRange]);
  const recent = useApi(() => getRecentCheckouts(range), [dateRange]);
  const refresh = () => { summary.refresh(); trend.refresh(); reasons.refresh(); recent.refresh(); };
  const stats = summary.data || {};
  const trendRows = trend.data?.items || [];
  const reasonRows = reasons.data?.items || [];
  const recentRows = recent.data?.items || [];
  const hasError = summary.networkError || trend.networkError || reasons.networkError || recent.networkError;

  const reasonChart = useMemo(
    () => reasonRows.map((row) => ({ name: row.reason, count: row.count, value: row.count })),
    [reasonRows],
  );

  const stat = (label, value, Icon) => (
    <StatCard label={label} value={summary.loading ? undefined : value} icon={Icon} sub="from persisted checkout sessions" />
  );

  return (
    <div className="page">
      {hasError ? <ErrorState error={summary.error || trend.error || reasons.error || recent.error} onRetry={refresh} /> : null}
      <section className="stats-grid">
        {stat('Checkout attempts', stats.total_checkout_attempts ?? '—', ShoppingCart)}
        {stat('Completed checkouts', stats.completed_checkouts ?? '—', CheckCircle2)}
        {stat('Drop-offs', stats.dropped_off_checkouts ?? '—', Clock3)}
        {stat('Conversion rate', stats.conversion_rate != null ? fmtPct(stats.conversion_rate) : '—', Percent)}
        {stat('Failed checkouts', stats.failed_checkouts ?? '—', XCircle)}
      </section>

      <section className="chart-grid two">
        <TrendChart
          title="Checkout Conversion Trend"
          subtitle="Attempts, completions and drop-offs from persisted sessions"
          data={trendRows}
          xKey="date"
          series={[
            { key: 'attempts', name: 'Attempts', color: '#6366f1' },
            { key: 'completed', name: 'Completed', color: '#10b981' },
            { key: 'dropped_off', name: 'Dropped off', color: '#f59e0b' },
          ]}
          loading={trend.loading}
          unavailable={trend.unavailable}
          networkError={trend.networkError}
          errorText={trend.error}
          onRetry={trend.refresh}
        />
        <BarChartView
          title="Drop-off Reasons"
          subtitle="Actual failure and drop-off reasons from checkout events"
          data={reasonChart}
          xKey="name"
          barKey="count"
          layout="vertical"
          loading={reasons.loading}
          unavailable={reasons.unavailable}
          networkError={reasons.networkError}
          errorText={reasons.error}
          onRetry={reasons.refresh}
        />
      </section>

      <Panel
        title="Recent Checkouts"
        subtitle={`${recentRows.length} persisted sessions · ${dateRange.label}`}
        actions={<Button variant="outline" size="sm" onClick={refresh}><RefreshCw size={13} /> Refresh</Button>}
        pad={false}
      >
        <DataTable
          loading={recent.loading}
          waiting={recent.unavailable}
          onRowClick={() => {}}
          minWidth={850}
          emptyTitle="No checkout sessions in this window"
          emptyDescription="Checkout records appear here after persisted checkout lifecycle events are received."
          defaultSort={{ key: 'created_at', dir: 'desc' }}
          columns={[
            { key: 'checkout_id', label: 'Checkout ID', sortable: true, className: 'mono', render: (r) => r.checkout_id || '—' },
            { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
            { key: 'amount', label: 'Amount', sortable: true, align: 'right', render: (r) => r.amount != null ? fmtINR(r.amount) : '—' },
            { key: 'checkout_status', label: 'Status', sortable: true, render: (r) => r.checkout_status || '—' },
            { key: 'failure_reason', label: 'Failure / drop-off reason', sortable: true, render: (r) => r.failure_reason || '—' },
            { key: 'created_at', label: 'Created At', sortable: true, render: (r) => fmtDateTime(r.created_at) },
          ]}
          rows={recentRows}
        />
      </Panel>
    </div>
  );
}
