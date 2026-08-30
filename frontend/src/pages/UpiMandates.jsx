import { useMemo } from 'react';
import { RefreshCw, WalletCards, CheckCircle2, XCircle, Clock3, Percent } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getMandates } from '../api';
import { useApp } from '../context/AppContext';
import { navigate } from '../hooks/useHashRoute';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { DataTable } from '../components/ui/DataTable';
import { MandateStatusBadge } from '../components/ui/StatusBadge';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { MandateDrawer } from '../components/mandates/MandateDrawer';
import { BarChartView } from '../components/charts/BarChartView';
import { TrendChart } from '../components/charts/TrendChart';
import { fmtINR, fmtPct, fmtDate, titleCase } from '../utils/format';
import { useState } from 'react';

const FREQ_LABEL = { monthly: 'Monthly', weekly: 'Weekly', daily: 'Daily', onemand: 'On demand' };

export function UpiMandates() {
  const { dateRange } = useApp();
  const [viewing, setViewing] = useState(null);

  const list = useApi(() => getMandates({ from: dateRange.from, to: dateRange.to }), [dateRange]);
  const grouped = useApi(
    () => getMandates({ from: dateRange.from, to: dateRange.to, group: 'day' }),
    [dateRange],
  );
  const rows = list.data?.items || list.data?.mandates || (Array.isArray(list.data) ? list.data : []);
  const counts = list.data?.counts || {};

  const stats = useMemo(() => {
    const out = {
      total: counts.total ?? list.data?.total ?? rows.length,
      active: counts.active ?? 0,
      failed: counts.failed ?? 0,
      pending: counts.pending ?? 0,
      successRate: null,
    };
    if (out.total > 0) out.successRate = (out.active / out.total) * 100;
    return out;
  }, [rows, counts, list.data]);

  const trend = useMemo(() => {
    return grouped.data?.items || [];
  }, [grouped.data]);

  const failureReasons = useMemo(() => {
    const byReason = {};
    rows.forEach((m) => {
      const st = String(m.status || '').trim().toLowerCase();
      if (!['failed', 'rejected'].includes(st)) return;
      const reason = String(m.failure_reason ?? m.failureReason ?? 'Unknown').trim().slice(0, 48) || 'Unknown';
      byReason[reason] = (byReason[reason] || 0) + 1;
    });
    return Object.entries(byReason)
      .map(([name, count]) => ({ name, count, value: count }));
  }, [rows]);

  const stat = (label, value, Icon, sub) => (
    <StatCard
      label={label}
      value={list.loading ? undefined : list.data ? value : 'No data available'}
      sub={list.networkError ? 'Backend offline' : list.unavailable ? 'Waiting for /api/mandates' : list.loading ? 'Loading…' : sub || 'from live mandate events'}
      icon={Icon}
    />
  );

  const openDrawer = (row) => {
    const id = row.id || row.mandate_id || row.rzp_mandate_id;
    if (id) setViewing(id);
  };

  return (
    <div className="page">
      <section className="stats-grid">
        {stat('Total mandates', String(stats.total), WalletCards)}
        {stat('Active mandates', String(stats.active), CheckCircle2, 'healthy recurring revenue')}
        {stat('Failed mandates', String(stats.failed), XCircle, 'needs attention')}
        {stat('Pending mandates', String(stats.pending), Clock3, 'awaiting first debit')}
        {stat('Success rate', fmtPct(stats.successRate), Percent, 'mandate activation rate')}
      </section>

      <section className="chart-grid">
        <TrendChart
          title="Mandate success / failure trend"
          subtitle="Mandate activations and failures over time (from live /api/mandates)"
          data={trend}
          xKey="date"
          series={[
            { key: 'active', name: 'Active', color: '#10b981' },
            { key: 'failed', name: 'Failed', color: '#ef4444' },
          ]}
          loading={list.loading || grouped.loading}
          unavailable={list.unavailable || grouped.unavailable}
          networkError={list.networkError || grouped.networkError}
          errorText={list.error || grouped.error}
          onRetry={() => { list.refresh(); grouped.refresh(); }}
        />
        <BarChartView
          title="Mandate failure reasons"
          subtitle="Why mandates fail to activate (live data)"
          data={failureReasons}
          xKey="name"
          barKey="count"
          layout="vertical"
          loading={list.loading}
          unavailable={list.unavailable}
          networkError={list.networkError}
          errorText={list.error}
          onRetry={list.refresh}
        />
      </section>

      <Panel
        title="Mandates"
         subtitle={`${list.data?.total ?? rows.length} mandates · ${dateRange.label}`}
        actions={
          <Button variant="outline" size="sm" onClick={() => { list.refresh(); grouped.refresh(); }}>
            <RefreshCw size={13} /> Refresh
          </Button>
        }
        pad={false}
      >
        {list.networkError ? (
          <ErrorState error={list.error} onRetry={list.refresh} />
        ) : (
          <DataTable
            loading={list.loading}
            waiting={list.unavailable}
            onRowClick={openDrawer}
            minWidth={900}
            emptyTitle="No mandates in this window"
            emptyDescription="UPI mandates will be listed here as the backend ingests Razorpay mandate events."
            defaultSort={{ key: 'created_at', dir: 'desc' }}
            columns={[
              { key: 'id', label: 'Mandate ID', sortable: true, className: 'mono', render: (r) => r.id || r.mandate_id || r.rzp_mandate_id || '—' },
              { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
              { key: 'amount', label: 'Amount', sortable: true, align: 'right', className: 'amount', sortValue: (r) => Number(r.amount || 0), render: (r) => (r.amount != null ? fmtINR(r.amount) : '—') },
              { key: 'frequency', label: 'Frequency', sortable: true, render: (r) => FREQ_LABEL[(r.frequency || '').toLowerCase()] || titleCase(r.frequency) || '—' },
              { key: 'status', label: 'Status', sortable: true, render: (r) => <MandateStatusBadge value={r.status} /> },
              { key: 'failure_reason', label: 'Failure reason', sortable: true, render: (r) => r.failure_reason || r.failureReason || '—' },
              { key: 'next_debit_at', label: 'Next debit', sortable: true, render: (r) => <span className="muted">{fmtDate(r.next_debit_at || r.nextDebitAt)}</span> },
              { key: 'created_at', label: 'Created date', sortable: true, render: (r) => <span className="muted">{fmtDate(r.created_at || r.createdAt)}</span> },
            ]}
            rows={rows}
          />
        )}
      </Panel>

      <MandateDrawer open={!!viewing} mandateId={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}
