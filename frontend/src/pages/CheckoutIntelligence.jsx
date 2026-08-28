import {
  Timer, RotateCcw, Layers, KeyRound, CheckCircle2, Repeat, RefreshCw,
  Activity, Monitor,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getCheckoutAnalytics } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { Panel } from '../components/ui/Panel';
import { WaitingState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { Button } from '../components/ui/Button';
import { ChartCard } from '../components/charts/ChartCard';
import { FunnelChart } from '../components/charts/FunnelChart';
import { TrendChart } from '../components/charts/TrendChart';
import { BarChartView } from '../components/charts/BarChartView';
import { CHECKOUT_STAGES } from '../types';
import { fmtNum, fmtCompact } from '../utils/format';

function SignalCard({ icon: Icon, label, value, loading }) {
  return (
    <div className="signal-card">
      <span className="icon-box">
        <Icon size={16} />
      </span>
      <div>
        <span className="signal-label">{label}</span>
        <strong>{loading ? '…' : value}</strong>
      </div>
    </div>
  );
}

export function CheckoutIntelligence() {
  const { dateRange } = useApp();
  const toast = useToast();

  const api = useApi(() => getCheckoutAnalytics({ from: dateRange.from, to: dateRange.to }), [dateRange]);
  const has = !!api.data && !api.loading;

  const funnel = api.data?.funnel || null;
  const signals = api.data?.signals || null;
  const dropoffByMethod = api.data?.dropoff_by_method || [];
  const dropoffByDevice = api.data?.dropoff_by_device || [];
  const dropoffTrend = api.data?.dropoff_trend || [];
  const investigation = api.data?.investigation || null;

  const funnelData = funnel ? funnel.map((f) => ({
    key: f.stage || f.key,
    label: CHECKOUT_STAGES[f.stage_index] || f.label || f.stage,
    value: f.value,
    count: f.count,
  })) : [];

  return (
    <div className="page">
      <div className="chart-grid reversed">
        <ChartCard
          title="Checkout conversion funnel"
          subtitle="Conversion rate at every stage of checkout"
          loading={api.loading}
          unavailable={api.unavailable}
          networkError={api.networkError}
          errorText={api.error}
          onRetry={api.refresh}
          hasData={funnelData.length > 0}
          height={340}
        >
          <FunnelChart data={funnelData} />
        </ChartCard>

        <Panel title="Behavioral signals" subtitle="What customers were doing during checkout">
          {!has ? (
            <WaitingState title={api.unavailable ? 'Waiting for checkout events' : 'No signals yet'} description={`Behavioral signals come from /api/checkout/analytics (session telemetry for ${dateRange.label}).`} />
          ) : (
            <div className="signal-grid">
              <SignalCard icon={Timer} label="Time on checkout" value={signals?.avg_time_on_checkout != null ? `${Math.round(signals.avg_time_on_checkout / 60)}m avg` : '—'} loading={api.loading} />
              <SignalCard icon={RotateCcw} label="Page reloads" value={signals?.page_reloads != null ? `${fmtNum(signals.page_reloads)} total` : '—'} loading={api.loading} />
              <SignalCard icon={Layers} label="Payment methods attempted" value={signals?.methods_attempted != null ? fmtNum(signals.methods_attempted) : '—'} loading={api.loading} />
              <SignalCard icon={KeyRound} label="OTP attempts" value={signals?.otp_attempts != null ? fmtNum(signals.otp_attempts) : '—'} loading={api.loading} />
              <SignalCard icon={CheckCircle2} label="OTP completion" value={signals?.otp_completion != null ? `${fmtNum(signals.otp_completion)} completed` : '—'} loading={api.loading} />
              <SignalCard icon={Repeat} label="Payment retries" value={signals?.payment_retries != null ? `${fmtNum(signals.payment_retries)} retries` : '—'} loading={api.loading} />
            </div>
          )}
        </Panel>
      </div>

      <section className="chart-grid two">
        <TrendChart
          title="Drop-off trend"
          subtitle="Checkout drop-off rate over time (source: /api/checkout/analytics?view=trend)"
          unavailable
          formatValue={(v) => `${v}%`}
        />
        <BarChartView
          title="Drop-off by method"
          subtitle="Where each payment method loses customers (source: /api/checkout/analytics?view=method)"
          unavailable
          layout="vertical"
        />
      </section>

      <section className="chart-grid two">
        <BarChartView
          title="Drop-off by device"
          subtitle="Mobile vs desktop checkout drop-offs (source: /api/checkout/analytics?view=device)"
          unavailable
          layout="vertical"
        />
        <Panel
          title="Drop-off signal mix"
          subtitle="Events that precede abandonment"
          actions={<Monitor size={15} className="muted-icon" />}
        >
          {!has ? (
            <WaitingState description="Signal mix is derived from checkout session events once the analytics API streams data." />
          ) : (
            <div className="dropoff-by">
              {dropoffByDevice.length > 0 ? dropoffByDevice.map((d, i) => (
                <div className="bar-legend-row" key={i}>
                  <span className="chip">{d.device || d.name || 'device'}</span>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(d.value, 100)}%`, background: i % 2 ? '#8b5cf6' : '#6366f1' }} /></div>
                  <strong>{fmtCompact(d.value)}</strong>
                </div>
              )) : <WaitingState title="No device data" description="Device-level drop-offs will appear once checkout telemetry is connected." />}
            </div>
          )}
        </Panel>
      </section>

      <Panel
        title="Drop-off investigation"
        subtitle="AI root-cause analysis of abandoned checkouts"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (api.unavailable || api.networkError) {
                toast('Investigation needs checkout events', 'info', {
                  description: 'The AI investigation runs once /api/checkout/analytics streams session telemetry.',
                });
              } else {
                api.refresh();
                toast('Investigation refreshed', 'success');
              }
            }}
          >
            <RefreshCw size={13} /> Run investigation
          </Button>
        }
      >
        {api.loading ? (
          <WaitingState title="Investigating…" />
        ) : api.unavailable ? (
          <WaitingState
            title="Waiting for checkout events"
            description="The AI investigation needs session telemetry. Enable checkout tracking and wire /api/checkout/analytics to analyze drop-offs like this: customer spent 5 minutes on checkout, reloaded 3 times, tried 2 payment methods, OTP was started but never completed."
          />
        ) : investigation ? (
          <div className="investigation-grid">
            <div className="detail-row"><span className="detail-label">Session behavior</span><span className="detail-value">{investigation.signal_summary || '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Likely cause</span><span className="detail-value">{investigation.likely_cause || '—'}</span></div>
            <div className="detail-row"><span className="detail-label">AI confidence</span><span className="detail-value">{investigation.confidence != null ? `${investigation.confidence}%` : '—'}</span></div>
            <div className="detail-row"><span className="detail-label">Recommended intervention</span><span className="detail-value">{investigation.recommended_intervention || '—'}</span></div>
          </div>
        ) : (
          <WaitingState title="No drop-off to investigate" description="The agent found no abandoned checkout sessions worth investigating in this window." />
        )}
      </Panel>
    </div>
  );
}