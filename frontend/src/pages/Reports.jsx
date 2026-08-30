import { useMemo, useState } from 'react';
import { RefreshCw, CheckCircle2, XCircle, IndianRupee, Percent, AlertTriangle, TrendingUp, FileText } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getReports } from '../api';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { TrendChart } from '../components/charts/TrendChart';
import { BarChartView } from '../components/charts/BarChartView';
import { fmtINR, fmtPct, fmtCompact, fmtNum, fmtDateTime } from '../utils/format';

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

function Change({ value }) {
  if (value?.label) return <span className="muted">Insufficient historical data</span>;
  if (value?.change_percent == null) return <span className="muted">—</span>;
  return <span className={value.change_percent >= 0 ? 'text-success' : 'text-danger'}>{value.change_percent >= 0 ? '+' : ''}{value.change_percent}% vs prior period</span>;
}

export function Reports() {
  const [period, setPeriod] = useState('7d');
  const api = useApi(() => getReports({ period }), [period]);
  const report = api.data;
  const summary = report?.summary;
  const paymentTrend = report?.trends?.payments || [];
  const checkoutTrend = report?.trends?.checkout || [];
  const failureReasons = report?.failure_reasons || [];
  const recoveryTrend = report?.trends?.recovery || [];
  const paymentMethods = useMemo(() => report?.payments?.method_performance || [], [report]);

  return (
    <div className="page">
      <Panel title="Operations report" subtitle="Live payment, checkout, anomaly, and recovery metrics from persisted data." actions={<div className="panel-actions">
        <div className="segmented">{PERIODS.map((item) => <button className={period === item.value ? 'active' : ''} key={item.value} onClick={() => setPeriod(item.value)}>{item.label}</button>)}</div>
        <Button variant="outline" size="sm" onClick={api.refresh}><RefreshCw size={13} /> Refresh</Button>
      </div>}>
        {api.loading ? <WaitingState title="Compiling report…" /> : api.networkError ? <ErrorState error={api.error} onRetry={api.refresh} /> : api.unavailable ? <WaitingState title="Report data unavailable" description="The report API is not reachable. No fallback values are displayed." /> : !report?.has_data ? <WaitingState title="No data available for this period." description="There are no persisted payment operations records in the selected period." /> : (
          <>
            <div className="report-meta"><span className="chip"><FileText size={12} /> {PERIODS.find((item) => item.value === period)?.label}</span><span className="muted">{report.range.from.slice(0, 10)} → {report.range.to.slice(0, 10)}</span></div>
            <section className="stats-grid">
              <StatCard label="Total payments" value={fmtNum(summary.total_payments)} sub={<Change value={report.comparisons.payment_volume} />} icon={FileText} />
              <StatCard label="Successful payments" value={fmtNum(summary.successful_payments)} sub={summary.success_rate != null ? fmtPct(summary.success_rate) : 'No rate available'} icon={CheckCircle2} />
              <StatCard label="Failed payments" value={fmtNum(summary.failed_payments)} sub={summary.failure_rate != null ? fmtPct(summary.failure_rate) : 'No rate available'} icon={XCircle} />
              <StatCard label="Payment volume" value={fmtINR(summary.payment_volume)} sub={<Change value={report.comparisons.payment_volume} />} icon={IndianRupee} />
              <StatCard label="Checkout attempts" value={fmtNum(summary.checkout_attempts)} sub={<Change value={report.comparisons.checkout_conversion} />} icon={FileText} />
              <StatCard label="Checkout conversion" value={summary.conversion_rate != null ? fmtPct(summary.conversion_rate) : '—'} sub={summary.checkout_dropoffs != null ? `${fmtCompact(summary.checkout_dropoffs)} drop-offs` : '—'} icon={Percent} />
              <StatCard label="Recovery opportunities" value={fmtCompact(summary.recovery_opportunities)} sub={`${fmtCompact(report.recovery.recommended)} recommended`} icon={TrendingUp} />
              <StatCard label="Detected anomalies" value={fmtCompact(summary.detected_anomalies)} sub={`${fmtCompact(report.anomalies.high + report.anomalies.critical)} high/critical`} icon={AlertTriangle} />
            </section>

            <div className="charts-grid">
              <TrendChart title="Payment performance trend" subtitle="Successful vs failed persisted payments" data={paymentTrend} xKey="date" series={[{ key: 'successful', name: 'Successful', color: '#16a34a' }, { key: 'failed', name: 'Failed', color: '#dc4b4b' }]} formatValue={fmtCompact} />
              <TrendChart title="Payment volume trend" subtitle="Payment amount by day" data={paymentTrend} xKey="date" series={[{ key: 'volume', name: 'Volume', color: '#6366f1' }]} formatValue={fmtINR} />
              <TrendChart title="Checkout conversion trend" subtitle="Attempts, completed, and dropped off" data={checkoutTrend} xKey="date" series={[{ key: 'attempts', name: 'Attempts', color: '#6366f1' }, { key: 'completed', name: 'Completed', color: '#16a34a' }, { key: 'dropped_off', name: 'Dropped off', color: '#e0703c' }]} formatValue={fmtCompact} />
              <BarChartView title="Payment failure reasons" subtitle="Persisted payment failure_reason values" data={failureReasons} xKey="name" barKey="count" color="#dc4b4b" formatValue={fmtCompact} />
              <BarChartView title="Recovery actions summary" subtitle="Persisted action statuses" data={recoveryTrend} xKey="name" barKey="value" color="#6366f1" formatValue={fmtCompact} />
            </div>

            <div className="report-columns">
              <Panel title="Anomaly summary" subtitle="Existing anomaly detector results" pad={false}>
                <div className="report-list"><div><span>Total</span><strong>{report.anomalies.total}</strong></div><div><span>Critical</span><strong>{report.anomalies.critical}</strong></div><div><span>High</span><strong>{report.anomalies.high}</strong></div><div><span>Medium</span><strong>{report.anomalies.medium}</strong></div></div>
                {(report.anomalies.recent || []).map((item) => <div className="report-row" key={item.id}><span>{item.type}</span><Status value={item.severity} /><span className="muted">{fmtDateTime(item.detected_at)}</span></div>)}
              </Panel>
              <Panel title="Recovery summary" subtitle="Existing recovery recommendations" pad={false}>
                <div className="report-list"><div><span>Opportunities</span><strong>{report.recovery.opportunities}</strong></div><div><span>High priority</span><strong>{report.recovery.high_priority}</strong></div><div><span>Medium priority</span><strong>{report.recovery.medium_priority}</strong></div><div><span>Completed</span><strong>{report.recovery.completed}</strong></div><div><span>Dismissed</span><strong>{report.recovery.dismissed}</strong></div></div>
              </Panel>
            </div>
            {paymentMethods.length > 0 && <Panel title="Payment method performance" subtitle="Method-level persisted payment outcomes" pad={false}><div className="bar-list">{paymentMethods.map((item) => <div className="bar-legend-row" key={item.method}><span className="chip">{item.method}</span><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(item.failure_rate, 100)}%` }} /></div><strong>{fmtPct(item.failure_rate)} failure</strong></div>)}</div></Panel>}
          </>
        )}
      </Panel>
    </div>
  );
}

function Status({ value }) {
  return <span className={`chip sev-${value}`}>{value}</span>;
}
