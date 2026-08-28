import { Sparkles, ArrowUpRight, Clock3 } from 'lucide-react';
import { Button } from '../ui/Button';
import { fmtCompact, fmtPct } from '../../utils/format';

export function AiInsightCard({ insight, onInvestigate }) {
  if (!insight) return null;
  const atRisk = insight.amount_at_risk ?? insight.amountAtRisk;
  return (
    <div className="ai-banner">
      <div className="ai-icon">
        <Sparkles size={18} />
      </div>
      <div className="ai-copy">
        <div className="ai-kicker">
          AI OPERATIONS INSIGHT
          {insight.detected_at || insight.detectedAt ? <span>{new Date(insight.detected_at ?? insight.detectedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span> : null}
        </div>
        <h3>{insight.issue || insight.message || 'AI Operations Insight'}</h3>
        {insight.cause ? <p><strong>Likely cause:</strong> {insight.cause}</p> : null}
        <div className="ai-insight-meta">
          {insight.affected_transactions != null ? <span>{insight.affected_transactions} affected transactions</span> : null}
          {atRisk != null ? <span>{fmtCompact(atRisk)} at risk</span> : null}
          {insight.confidence != null ? <span>Confidence {fmtPct(insight.confidence)}</span> : null}
        </div>
      </div>
      <div className="ai-metrics">
        {atRisk != null ? (
          <div>
            <span>At risk</span>
            <strong>{fmtCompact(atRisk)}</strong>
          </div>
        ) : null}
        {insight.confidence != null ? (
          <div>
            <span>Confidence</span>
            <strong>{fmtPct(insight.confidence)}</strong>
          </div>
        ) : null}
      </div>
      {(insight.recommended_action || insight.action) && (
        <div className="ai-reco-text">{insight.recommended_action || insight.action}</div>
      )}
      <Button icon={ArrowUpRight} onClick={() => onInvestigate?.()}>
        Investigate
      </Button>
    </div>
  );
}

export function AiInsightWaiting({ onInvestigate, time }) {
  return (
    <div className="ai-banner muted-banner">
      <div className="ai-icon">
        <Clock3 size={18} />
      </div>
      <div className="ai-copy">
        <div className="ai-kicker">AI OPERATIONS INSIGHT</div>
        <h3>Waiting for payment events</h3>
        <p>The agent generates insights after it establishes a baseline from live payment events. Insights will appear here as the backend streams data.</p>
        {time ? <div className="ai-insight-meta"><span>Baseline window: {time}</span></div> : null}
      </div>
      <Button variant="outline" onClick={() => onInvestigate?.()}>
        Open AI Agent
      </Button>
    </div>
  );
}