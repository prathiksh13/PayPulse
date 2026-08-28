import { Lightbulb, Play, Eye, ShieldAlert } from 'lucide-react';
import { fmtPct } from '../../utils/format';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

function RiskBadge({ risk }) {
  const tones = { low: 'success', medium: 'warning', high: 'danger', critical: 'danger' };
  if (!risk) return null;
  return <Badge tone={tones[risk] || 'muted'}>{String(risk).toUpperCase()} risk</Badge>;
}

/**
 * One AI recommendation with Recommendation / Reason / Confidence /
 * Expected impact / Risk / Evidence, plus Execute + Review actions.
 */
export function AiRecommendationCard({
  recommendation, reason, confidence, impact, risk, evidence, id,
  onExecute, onReview, executing = false, borderTone = 'indigo',
}) {
  return (
    <div className={`ai-reco ai-reco-${borderTone}`}>
      <div className="ai-reco-head">
        <div className="ai-reco-icon">
          <Lightbulb size={16} />
        </div>
        <div className="ai-reco-title">
          <strong>{recommendation || 'Recommended action'}</strong>
          {risk ? <RiskBadge risk={risk} /> : null}
        </div>
        <div className="ai-reco-confidence">
          <span>Confidence</span>
          <strong>{fmtPct(confidence)}</strong>
        </div>
      </div>
      {reason ? (
        <div className="ai-reco-row">
          <span className="ai-row-label">Reason</span>
          <p>{reason}</p>
        </div>
      ) : null}
      {impact ? (
        <div className="ai-reco-row">
          <span className="ai-row-label">Expected impact</span>
          <p>{typeof impact === 'object' ? (impact.note || impact.amount || JSON.stringify(impact)) : impact}</p>
        </div>
      ) : null}
      {evidence ? (
        <div className="ai-reco-evidence">
          <span className="ai-row-label">Evidence</span>
          <div className="evidence-chips">
            {Array.isArray(evidence)
              ? evidence.map((e, i) => <span key={i} className="chip">{typeof e === 'object' ? (e.label || JSON.stringify(e)) : e}</span>)
              : <span className="chip">{evidence}</span>}
          </div>
        </div>
      ) : null}
      <div className="ai-reco-actions">
        <Button size="sm" icon={Play} onClick={() => onExecute?.(id)} loading={executing} disabled={!onExecute}>
          Execute
        </Button>
        <Button size="sm" variant="outline" icon={Eye} onClick={() => onReview?.(id)}>
          Review
        </Button>
      </div>
    </div>
  );
}

export function RecommendationFallback({ title = 'No active recommendations', description = 'The AI agent will recommend recovery actions as it detects issues across your payment flow.' }) {
  return (
    <div className="ai-reco-fallback">
      <div className="ai-reco-icon">
        <ShieldAlert size={16} />
      </div>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}