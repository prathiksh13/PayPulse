import { AGENT_PIPELINE } from '../../types';
import { Eye, Radar, Brain, Lightbulb, CheckCircle2, Zap, GraduationCap } from 'lucide-react';

const ICONS = {
  observe: Eye,
  detect: Radar,
  infer: Brain,
  recommend: Lightbulb,
  approve: CheckCircle2,
  execute: Zap,
  learn: GraduationCap,
};

/**
 * Visualizes Observe → Detect → Infer → Recommend → Approve → Execute → Learn.
 * `status` may map pipeline keys to 'done' | 'active' | 'waiting' | 'skipped';
 * when absent, stages render neutral "waiting for events".
 */
export function AiDecisionTimeline({ status = {}, waiting = true }) {
  return (
    <div className="ai-pipeline">
      {AGENT_PIPELINE.map((stage, i) => {
        const Icon = ICONS[stage.key] || Brain;
        const st = status[stage.key] || (waiting ? 'waiting' : 'active');
        return (
          <div key={stage.key} className={`pipeline-step step-${st}`}>
            <div className="pipeline-connector">{i > 0 ? <span /> : null}</div>
            <div className="pipeline-icon">
              <Icon size={15} />
            </div>
            <div className="pipeline-copy">
              <strong>{stage.label}</strong>
              <span>{stage.description}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}