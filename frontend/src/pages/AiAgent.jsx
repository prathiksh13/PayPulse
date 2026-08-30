import {
  Bot, Radar, SearchCheck, Lightbulb, Zap, IndianRupee, AlertTriangle,
  Activity,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getAgentStatus, getAgentInvestigations } from '../api';
import { useApp } from '../context/AppContext';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { AiDecisionTimeline } from '../components/agent/AiDecisionTimeline';
import { AgentChat } from '../components/agent/AgentChat';
import { fmtCompact, fmtNum, fmtPct, fmtDateTime } from '../utils/format';

export function AiAgent() {
  const { dateRange, settings } = useApp();

  const statusApi = useApi(getAgentStatus, []);
  const invApi = useApi(getAgentInvestigations, []);

  const status = statusApi.data || {};
  const investigations = invApi.data?.items || invApi.data?.investigations || (Array.isArray(invApi.data) ? invApi.data : []);
  const engaged = !statusApi.unavailable && !statusApi.networkError && !!statusApi.data;

  const pipelineStatus = status.pipeline || (engaged ? null : {});

  const investigation = investigations[0] || null;

  return (
    <div className="page">
      <div className="api-banner ai-tint">
        <div>
          <strong>AI agent {settings.aiEnabled ? 'enabled' : 'disabled'} · {settings.requireApproval ? 'approval required' : 'auto-approve'}</strong>
          <span>
            {statusApi.networkError
              ? 'Backend offline — the agent cannot watch payments. Start the FastAPI server.'
              : statusApi.unavailable
                ? 'Waiting for agent endpoints (GET /api/agent/status). The command center fills as the agent connects.'
                : `The agent is actively monitoring payment health across ${dateRange.label}.`}
          </span>
        </div>
        <div className="agent-badges">
          <span className={`pill ${engaged ? 'live' : ''}`}>{engaged ? <span className="pulse-dot" /> : null} {engaged ? 'Online' : 'Standby'}</span>
        </div>
      </div>

      <section className="stats-grid">
        <StatCard label="Agent status" value={engaged ? 'Online' : 'Standby'} sub="watching payment events" icon={Bot} />
        <StatCard label="Issues detected" value={engaged ? fmtNum(status.issues_detected) : 'No data available'} sub="in monitoring window" icon={Radar} />
        <StatCard label="Investigations" value={engaged ? fmtNum(status.investigations) : 'No data available'} sub="AI root-cause analysis" icon={SearchCheck} />
        <StatCard label="Recommended actions" value={engaged ? fmtNum(status.recommended_actions) : 'No data available'} sub="awaiting approval" icon={Lightbulb} />
        <StatCard label="Actions executed" value={engaged ? fmtNum(status.actions_executed) : 'No data available'} sub="with guardrails" icon={Zap} />
        <StatCard label="Estimated recovered revenue" value={engaged ? fmtCompact(status.recovered_revenue) : 'No data available'} sub="from executed actions" icon={IndianRupee} />
      </section>

      <section className="ai-grid">
        <Panel title="AI decision pipeline" subtitle="Observe → Detect → Infer → Recommend → Approve → Execute → Learn">
          <AiDecisionTimeline status={pipelineStatus} waiting={!engaged} />
          <div className="pipeline-note muted">
            {!engaged
              ? 'Stage states populate once the agent API streams events and tool-call results.'
              : `Last activity: ${fmtDateTime(status.last_active_at || status.updated_at)}`}
          </div>
        </Panel>

        <Panel title="AI investigation" subtitle={investigation ? investigation.type || 'Current issue' : 'No active investigation'} actions={<Activity size={16} className="muted-icon" />}>
          {invApi.loading ? (
            <WaitingState title="Investigating…" />
          ) : invApi.networkError ? (
            <ErrorState error={invApi.error} onRetry={invApi.refresh} />
          ) : invApi.unavailable ? (
            <WaitingState
              title="Waiting for agent investigations"
              description="Investigation cards — what happened, when it started, affected methods, amount at risk, root cause and confidence — appear here from GET /api/agent/investigations."
            />
          ) : !investigation ? (
            <WaitingState title="No active investigation" description="The agent will start an investigation the next time it detects an anomaly." />
          ) : (
            <div className="investigation-card">
              <div className="invest-head">
                <AlertTriangle size={16} />
                <strong>{investigation.issue || investigation.type || 'Issue detected'}</strong>
              </div>
              <div className="detail-grid">
                <div className="detail-row"><span className="detail-label">What happened</span><span className="detail-value">{investigation.what_happened || '—'}</span></div>
                <div className="detail-row"><span className="detail-label">When it started</span><span className="detail-value">{fmtDateTime(investigation.started_at || investigation.detected_at)}</span></div>
                <div className="detail-row"><span className="detail-label">Affected methods</span><span className="detail-value">{investigation.affected_methods?.join(', ') || '—'}</span></div>
                <div className="detail-row"><span className="detail-label">Affected amount</span><span className="detail-value">{investigation.affected_amount != null ? fmtCompact(investigation.affected_amount) : '—'}</span></div>
                <div className="detail-row"><span className="detail-label">Likely root cause</span><span className="detail-value">{investigation.root_cause || investigation.likely_cause || '—'}</span></div>
                <div className="detail-row"><span className="detail-label">Confidence</span><span className="detail-value">{investigation.confidence != null ? fmtPct(investigation.confidence) : '—'}</span></div>
              </div>
              <div className="drawer-actions">
                <Button size="sm" variant="outline" onClick={() => toast('Investigation context loaded', 'info', { description: investigation.id })}>
                  View evidence
                </Button>
              </div>
            </div>
          )}
        </Panel>
      </section>

      <AgentChat dateRange={dateRange} />
    </div>
  );
}
