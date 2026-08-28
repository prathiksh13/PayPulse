import { useState } from 'react';
import { RefreshCw, RotateCcw, Ban, Mail, ArrowUpRight, History } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { invalidateCache, getRecoveryActions, executeRecoveryAction, getRecoveryHistory } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { Panel } from '../components/ui/Panel';
import { DataTable } from '../components/ui/DataTable';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { RECOVERY_STATUS, RECOVERY_ACTION_TYPE } from '../types';
import { fmtINR, fmtPct, fmtDateTime, titleCase } from '../utils/format';

const ACTION_TONE = {
  retry: { label: 'Retry', btn: 'outline' },
  refund: { label: 'Refund', btn: 'danger' },
  notify: { label: 'Notify', btn: 'outline' },
  escalate: { label: 'Escalate', btn: 'outline' },
  ignore: { label: 'Ignore', btn: 'ghost' },
};

const DANGEROUS_ACTIONS = ['refund', 'ignore'];
const HISTORY_COLUMNS = [
  { key: 'action', label: 'Action', sortable: true, render: (r) => titleCase(r.action) },
  { key: 'payment_id', label: 'Payment', sortable: true, className: 'mono', render: (r) => r.payment_id || r.payment },
  { key: 'executed_by', label: 'Executed by', sortable: true, render: (r) => r.executed_by || r.by || 'AI Agent' },
  { key: 'created_at', label: 'Time', sortable: true, render: (r) => <span className="muted">{fmtDateTime(r.created_at || r.createdAt)}</span> },
  { key: 'result', label: 'Result', sortable: true, render: (r) => <StatusBadge value={r.result || r.status} meta={{ success: { label: 'Success', tone: 'success' }, failed: { label: 'Failed', tone: 'danger' }, pending: { label: 'Pending', tone: 'warning' } }} /> },
];

const ACTIVE_STATUSES = ['failed', 'attempted', 'pending', 'in_progress'];

const canRetry = (r) => {
  const st = String(r.payment_status || '').toLowerCase();
  return r.payment_status == null ? true : ACTIVE_STATUSES.includes(st);
};

const canRefundAction = (r) => {
  const st = String(r.payment_status || '').toLowerCase();
  // Refund is only shown for captured/authorized payments; failed-never-captured
  // payments cannot be refunded and there is no way to allow it via a recovery
  // row on a captured payment either unless the backend says it is valid.
  return r.payment_status == null ? true : st === 'captured' || st === 'authorized';
};

export function RecoveryActions() {
  const { dateRange } = useApp();
  const toast = useToast();

  const actionsApi = useApi(() => getRecoveryActions({ from: dateRange.from, to: dateRange.to }), [dateRange]);
  const histApi = useApi(() => getRecoveryHistory({ from: dateRange.from, to: dateRange.to }), [dateRange]);

  const rows = actionsApi.data?.items || actionsApi.data?.actions || (Array.isArray(actionsApi.data) ? actionsApi.data : []);
  const history = histApi.data?.items || histApi.data?.history || (Array.isArray(histApi.data) ? histApi.data : []);

  const [pending, setPending] = useState(null); // {row, action}

  const runAction = async () => {
    if (!pending) return;
    const { row, action } = pending;
    const res = await executeRecoveryAction(row.id, action);
    setPending(null);
    if (res.ok) {
      toast(`${RECOVERY_ACTION_TYPE[action]?.label || titleCase(action)} executed`, 'success', { description: `${row.id} — backend is processing.` });
      await invalidateCache().catch(() => {});
      actionsApi.refresh();
      histApi.refresh();
    } else if (res.status === 404) {
      toast('Recovery endpoint pending', 'error', {
        description: `POST /api/recovery/actions/${row.id}/execute is not implemented yet. Wire it to actually ${action} this payment.`,
      });
    } else {
      toast('Action failed', 'error', { description: res.error });
    }
  };

  const openAction = (row, action) => {
    const meta = ACTION_TONE[action];
    setPending({ row, action, meta });
  };

  const columns = [
    { key: 'payment', label: 'Payment', sortable: true, className: 'mono', render: (r) => r.payment_id || r.payment || r.id || '—' },
    { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
    { key: 'failure_reason', label: 'Failure reason', sortable: true, render: (r) => r.failure_reason || r.failureReason || '—' },
    { key: 'recommended_action', label: 'Recommended action', sortable: true, render: (r) => r.recommended_action || r.action || '—' },
    { key: 'recovery_probability', label: 'Recovery probability', sortable: true, sortValue: (r) => Number(r.recovery_probability ?? r.probability ?? r.confidence ?? 0), align: 'right', render: (r) => fmtPct(r.recovery_probability ?? r.probability ?? r.confidence) },
    { key: 'amount', label: 'Amount', sortable: true, align: 'right', className: 'amount', sortValue: (r) => Number(r.amount || 0), render: (r) => (r.amount != null ? fmtINR(r.amount) : '—') },
    { key: 'risk', label: 'Risk', sortable: true, render: (r) => (r.risk ? <StatusBadge value={r.risk} meta={{ low: { label: 'Low', tone: 'success' }, medium: { label: 'Medium', tone: 'warning' }, high: { label: 'High', tone: 'danger' }, critical: { label: 'Critical', tone: 'danger' } }} /> : '—') },
    { key: 'status', label: 'Status', sortable: true, render: (r) => <StatusBadge value={r.status} meta={RECOVERY_STATUS} /> },
    {
      key: '_actions', label: 'Actions', className: 'actions-col',
      render: (r) => (
        <div className="row-actions">
          {canRetry(r) && <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); openAction(r, 'retry'); }}><RefreshCw size={13} /> Retry</Button>}
          {canRefundAction(r) && <Button size="sm" variant="danger" onClick={(e) => { e.stopPropagation(); openAction(r, 'refund'); }}><RotateCcw size={13} /> Refund</Button>}
          <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); openAction(r, 'notify'); }}><Mail size={13} /> Notify</Button>
          <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); openAction(r, 'escalate'); }}><ArrowUpRight size={13} /> Escalate</Button>
          <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); openAction(r, 'ignore'); }}><Ban size={13} /> Ignore</Button>
        </div>
      ),
    },
  ];

  return (
    <div className="page">
      <div className="intro-strip">
        <div>
          <strong>Recovery operations</strong>
          <span>Every action requires a confirmation. Guardrails (max retries, max amount, risk threshold) are enforced by the backend.</span>
        </div>
        <Button variant="outline" size="sm" onClick={actionsApi.refresh}><RefreshCw size={13} /> Refresh</Button>
      </div>

      <Panel
        title="Recovery opportunities"
        subtitle={`${rows.length} ranked opportunities · ${dateRange.label}`}
        pad={false}
      >
        {actionsApi.networkError ? (
          <ErrorState error={actionsApi.error} onRetry={actionsApi.refresh} />
        ) : (
          <DataTable
            loading={actionsApi.loading}
            waiting={actionsApi.unavailable}
            minWidth={1180}
            emptyTitle="No recovery opportunities"
            emptyDescription="AI-ranked payouts appear here from /api/recovery/actions. Nothing to recover right now."
            columns={columns}
            rows={rows}
          />
        )}
      </Panel>

      <Panel
        title="Action history"
        subtitle={`${history.length} executed actions log · ${dateRange.label}`}
        actions={<History size={16} className="muted-icon" />}
        pad={false}
      >
        {histApi.networkError ? (
          <ErrorState error={histApi.error} onRetry={histApi.refresh} />
        ) : (
          <DataTable
            loading={histApi.loading}
            waiting={histApi.unavailable}
            minWidth={720}
            emptyTitle="No actions executed yet"
            emptyDescription="Approved recovery actions will be logged here (source: /api/recovery/actions/history)."
            columns={HISTORY_COLUMNS}
            rows={history}
          />
        )}
      </Panel>

      <ConfirmDialog
        open={!!pending}
        onClose={() => setPending(null)}
        onConfirm={runAction}
        title={`${pending?.meta?.label || 'Run'} recovery action?`}
        description={
          pending
            ? `${pending.meta?.label} on ${pending.row.payment_id || pending.row.id} (${pending.row.amount != null ? fmtINR(pending.row.amount) : '—'}). This is sent to POST /api/recovery/actions/${pending.row.id}/execute for backend approval and execution.`
            : undefined
        }
        confirmLabel={pending?.meta?.label || 'Confirm'}
        danger={pending ? DANGEROUS_ACTIONS.includes(pending.action) : false}
      />
    </div>
  );
}