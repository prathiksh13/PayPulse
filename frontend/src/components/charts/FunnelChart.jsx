import { ArrowDown } from 'lucide-react';
import { fmtPct } from '../../utils/format';

/**
 * Vertical funnel. `data`: [{ key, label, value, count? }].
 * `value` expected to be a percentage (0-100) of checkout-started;
 * conversion between stages is derived.
 */
export function FunnelChart({ data = [], fromLabel = 'total users' }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.value || 0), 1);
  return (
    <div className="funnel">
      {data.map((stage, i) => {
        const prev = i > 0 ? data[i - 1] : null;
        const conv = prev ? ((stage.value || 0) / (prev.value || 1)) * 100 : 100;
        const widthPct = Math.max((stage.value / max) * 100, 8);
        return (
          <div key={stage.key || stage.label} className="funnel-row">
            <div className="funnel-stage">
              <div className="funnel-track">
                <div className="funnel-fill" style={{ width: `${widthPct}%` }}>
                  <span className="funnel-count">
                    {stage.count != null ? stage.count : fmtPct(stage.value)}
                  </span>
                </div>
              </div>
              <div className="funnel-meta">
                <strong>{stage.label}</strong>
                <span>of {fromLabel}</span>
              </div>
              <div className="funnel-rate">{fmtPct(stage.value)}</div>
            </div>
            {i < data.length - 1 ? (
              <div className="funnel-link">
                <ArrowDown size={13} />
                <span>conversion {fmtPct(conv)}</span>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}