import { useMemo, useState } from 'react';
import { CreditCard, FilterX, Search, RefreshCw } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { useDebounce } from '../hooks/useDebounce';
import { getPayments } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { navigate } from '../hooks/useHashRoute';
import { Panel } from '../components/ui/Panel';
import { DataTable } from '../components/ui/DataTable';
import { Field, TextInput, Select } from '../components/ui/Field';
import { PaymentStatusBadge } from '../components/ui/StatusBadge';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { PaymentDrawer } from '../components/payments/PaymentDrawer';
import { TestPaymentModal } from '../components/payments/TestPaymentModal';
import { fmtINR, titleCase, fmtDateTime } from '../utils/format';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'success', label: 'Success' },
  { value: 'failed', label: 'Failed' },
  { value: 'pending', label: 'Pending' },
  { value: 'refunded', label: 'Refunded' },
  { value: 'partially_refunded', label: 'Partially refunded' },
];

const METHOD_OPTIONS = [
  { value: '', label: 'All methods' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
  { value: 'netbanking', label: 'Netbanking' },
  { value: 'wallet', label: 'Wallet' },
  { value: 'emi', label: 'EMI' },
];

export function Payments() {
  const { dateRange } = useApp();
  const toast = useToast();

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [method, setMethod] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const debouncedSearch = useDebounce(search, 350);

  const routeQuery = new URLSearchParams(window.location.hash.split('?')[1] || '');
  const [viewing, setViewing] = useState(routeQuery.get('view') || null);

  const params = useMemo(
    () => ({
      from: dateRange.from,
      to: dateRange.to,
      query: debouncedSearch || undefined,
      status: status || undefined,
      method: method || undefined,
      min_amount: minAmount ? Number(minAmount) : undefined,
      max_amount: maxAmount ? Number(maxAmount) : undefined,
    }),
    [dateRange, debouncedSearch, status, method, minAmount, maxAmount],
  );

  const payments = useApi(() => getPayments(params), [params]);
  const rows = payments.data?.items || payments.data?.payments || (Array.isArray(payments.data) ? payments.data : []);

  const [testPayOpen, setTestPayOpen] = useState(false);

  const hasActiveFilters = search || status || method || minAmount || maxAmount;
  const clearFilters = () => {
    setSearch('');
    setStatus('');
    setMethod('');
    setMinAmount('');
    setMaxAmount('');
    toast('Filters cleared', 'info');
  };

  const openDrawer = (row) => {
    const id = row.id || row.payment_id || row.rzp_payment_id;
    if (!id) return;
    setViewing(id);
    navigate(`/payments?view=${encodeURIComponent(id)}`);
  };

  const closeDrawer = () => {
    setViewing(null);
    navigate('/payments');
  };

  return (
    <div className="page">
      <Panel
        title="All transactions"
        subtitle={`${rows.length} records loaded · ${dateRange.label}`}
        actions={
          <>
            <Button variant="primary" size="sm" icon={CreditCard} onClick={() => setTestPayOpen(true)}>
              Make Test Payment
            </Button>
            <Button variant="outline" size="sm" onClick={payments.refresh}>
              <RefreshCw size={13} /> Refresh
            </Button>
          </>
        }
        pad={false}
      >
        <div className="filter-bar">
          <Field className="grow">
            <TextInput
              type="search"
              placeholder="Search payment ID, order ID or customer…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Field>
          <Field>
            <Select value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </Field>
          <Field>
            <Select value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </Field>
          <Field>
            <div className="amount-range">
              <TextInput type="number" placeholder="Min ₹" value={minAmount} onChange={(e) => setMinAmount(e.target.value)} aria-label="Minimum amount" />
              <TextInput type="number" placeholder="Max ₹" value={maxAmount} onChange={(e) => setMaxAmount(e.target.value)} aria-label="Maximum amount" />
            </div>
          </Field>
          {hasActiveFilters ? (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <FilterX size={13} /> Clear
            </Button>
          ) : (
            <span className="filter-count muted">
              <Search size={13} /> Filtering applies to /api/payments
            </span>
          )}
        </div>

        {payments.networkError ? (
          <ErrorState error={payments.error} onRetry={payments.refresh} />
        ) : (
          <DataTable
            loading={payments.loading}
            waiting={payments.unavailable}
            onRowClick={openDrawer}
            minWidth={900}
            emptyTitle="No payments match the current filters"
            emptyDescription="Confirm the date range, or clear filters to widen the search."
            defaultSort={{ key: 'created_at', dir: 'desc' }}
            columns={[
              { key: 'id', label: 'Payment ID', sortable: true, className: 'mono', render: (r) => r.id || r.payment_id || '—' },
              { key: 'order_id', label: 'Order ID', sortable: true, className: 'mono', render: (r) => r.order_id || r.orderId || '—' },
              { key: 'amount', label: 'Amount', sortable: true, align: 'right', className: 'amount', sortValue: (r) => Number(r.amount || 0), render: (r) => (r.amount != null ? fmtINR(r.amount) : '—') },
              { key: 'method', label: 'Method', sortable: true, render: (r) => (r.method ? titleCase(r.method) : '—') },
              { key: 'status', label: 'Status', sortable: true, render: (r) => <PaymentStatusBadge value={r.status} /> },
              { key: 'failure_reason', label: 'Failure reason', sortable: true, render: (r) => r.failure_reason || r.failureReason || '—' },
              { key: 'created_at', label: 'Created time', sortable: true, sortValue: (r) => new Date(r.created_at || r.createdAt || 0).getTime(), render: (r) => <span className="muted">{fmtDateTime(r.created_at || r.createdAt)}</span> },
              { key: 'customer', label: 'Customer', sortable: true, render: (r) => r.customer?.name || r.customer_name || '—' },
            ]}
            rows={rows}
          />
        )}
      </Panel>

      <PaymentDrawer
        open={!!viewing}
        paymentId={viewing}
        onClose={closeDrawer}
        onRecovery={(p) => {
          closeDrawer();
          navigate('/recovery');
          toast('Recovery review opened', 'info', { description: p.id });
        }}
      />

      <TestPaymentModal
        open={testPayOpen}
        onClose={() => setTestPayOpen(false)}
        onComplete={() => payments.refresh()}
      />
    </div>
  );
}