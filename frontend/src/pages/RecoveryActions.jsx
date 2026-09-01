import { useMemo, useState } from 'react';
import { RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getRecoveryActions, updateRecoveryActionStatus } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { DataTable } from '../components/ui/DataTable';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { Select, Field } from '../components/ui/Field';
import { StatusBadge } from '../components/ui/StatusBadge';
import { RECOVERY_STATUS } from '../types';
import { fmtINR, fmtDateTime } from '../utils/format';

export function RecoveryActions() {
  const { dateRange } = useApp();
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [priorityFilter, setPriorityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const actionsApi = useApi(() => getRecoveryActions({ from: dateRange.from, to: dateRange.to }), [dateRange]);
  const rows = actionsApi.data?.items || actionsApi.data?.actions || [];
  const filteredRows = useMemo(() => rows.filter((row) =>
    (!priorityFilter || row.risk === priorityFilter) && (!statusFilter || row.status === statusFilter)
  ), [rows, priorityFilter, statusFilter]);
  const counts = useMemo(() => ({
    total: rows.length,
    high: rows.filter((r) => r.risk === 'high' || r.risk === 'critical').length,
    medium: rows.filter((r) => r.risk === 'medium').length,
    pending: rows.filter((r) => ['recommended', 'pending', 'in_progress'].includes(r.status)).length,
    completed: rows.filter((r) => r.status === 'completed' || r.status === 'executed').length,
  }), [rows]);

  const setStatus = async (row, status) => {
    const response = await updateRecoveryActionStatus(row.id, status);
    if (!response.ok) {
      toast('Status update failed', 'error', { description: response.error });
      return;
    }
    toast('Recovery status updated', 'success', { description: `${row.id} is now ${status}.` });
    actionsApi.refresh();
  };

  const columns = [
    { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
    { key: 'source', label: 'Payment / Checkout', sortable: true, className: 'mono', render: (r) => r.checkout_id || r.payment_id || '—' },
    { key: 'amount', label: 'Amount', sortable: true, align: 'right', className: 'amount', render: (r) => r.amount != null ? fmtINR(r.amount) : '—' },
    { key: 'issue', label: 'Problem', sortable: true, render: (r) => r.issue || r.reason || '—' },
    { key: 'failure_reason', label: 'Failure reason', sortable: true, render: (r) => r.failure_reason || '—' },
    { key: 'recommended_action', label: 'Recommended action', sortable: true, render: (r) => r.recommended_action || 'Needs investigation' },
    { key: 'risk', label: 'Priority', sortable: true, render: (r) => <StatusBadge value={r.risk} meta={{ low: { label: 'Low', tone: 'info' }, medium: { label: 'Medium', tone: 'warning' }, high: { label: 'High', tone: 'danger' }, critical: { label: 'Critical', tone: 'danger' } }} /> },
    { key: 'status', label: 'Status', sortable: true, render: (r) => <StatusBadge value={r.status} meta={{ ...RECOVERY_STATUS, recommended: { label: 'Recommended', tone: 'info' }, completed: { label: 'Completed', tone: 'success' }, dismissed: { label: 'Dismissed', tone: 'muted' } }} /> },
    { key: 'created_at', label: 'Created', sortable: true, render: (r) => fmtDateTime(r.created_at || r.createdAt) },
    { key: '_actions', label: 'Status', render: (r) => (
      isAdmin ? (
        <div className="row-actions">
          {r.status === 'recommended' && <Button size="sm" variant="outline" onClick={() => setStatus(r, 'in_progress')}>Investigate</Button>}
          {['recommended', 'in_progress'].includes(r.status) && <Button size="sm" variant="outline" onClick={() => setStatus(r, 'completed')}><CheckCircle2 size={13} /> Complete</Button>}
          {['recommended', 'in_progress'].includes(r.status) && <Button size="sm" variant="ghost" onClick={() => setStatus(r, 'dismissed')}>Dismiss</Button>}
        </div>
      ) : (
        <span className="text-muted">View only</span>
      )
    ) },
  ];

  return (
    <div className="page">
      <section className="stats-grid">
        <StatCard label="Total opportunities" value={actionsApi.data ? counts.total : 'No data available'} sub="from failed payments and abandoned checkouts" icon={AlertTriangle} />
        <StatCard label="High priority" value={actionsApi.data ? counts.high : 'No data available'} sub="repeated or high-value issues" icon={AlertTriangle} />
        <StatCard label="Medium priority" value={actionsApi.data ? counts.medium : 'No data available'} sub="normal recovery opportunities" icon={RefreshCw} />
        <StatCard label="Completed" value={actionsApi.data ? counts.completed : 'No data available'} sub="status tracked only" icon={CheckCircle2} />
      </section>
      <Panel title="Recovery opportunities" subtitle={`${filteredRows.length} opportunities · ${dateRange.label}`} actions={<div className="panel-actions">
        <Field><Select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}><option value="">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></Select></Field>
        <Field><Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="">All statuses</option><option value="recommended">Recommended</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="dismissed">Dismissed</option></Select></Field>
        <Button variant="outline" size="sm" onClick={actionsApi.refresh}><RefreshCw size={13} /> Refresh</Button>
      </div>} pad={false}>
        {actionsApi.networkError ? <ErrorState error={actionsApi.error} onRetry={actionsApi.refresh} /> : actionsApi.unavailable ? <WaitingState title="Waiting for recovery data" description="Recovery recommendations appear here from the live payments and checkout records." /> : <DataTable loading={actionsApi.loading} emptyTitle="No recovery opportunities" emptyDescription="No failed payment or abandoned checkout currently needs investigation." columns={columns} rows={filteredRows} minWidth={1500} />}
      </Panel>
    </div>
  );
}
