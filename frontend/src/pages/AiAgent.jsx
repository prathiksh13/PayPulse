import { useState } from 'react';
import {
  Bot, Radar, SearchCheck, Lightbulb, Zap, IndianRupee, AlertTriangle,
  Activity, RefreshCw,
} from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { getAgentStatus, getAgentInvestigations, getRecoveryActions, executeRecoveryAction } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { navigate } from '../hooks/useHashRoute';
import { Panel } from '../components/ui/Panel';
import { StatCard } from '../components/ui/StatCard';
import { Button } from '../components/ui/Button';
import { ErrorState } from '../components/ui/ErrorState';
import { WaitingState } from '../components/ui/EmptyState';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import { AiDecisionTimeline } from '../components/agent/AiDecisionTimeline';
import { AiRecommendationCard, RecommendationFallback } from '../components/agent/AiRecommendationCard';
import { AgentChat } from '../components/agent/AgentChat';
import { fmtCompact, fmtNum, fmtPct, fmtDateTime } from '../utils/format';

export function AiAgent() {
  const { dateRange, settings } = useApp();
  const toast = useToast();

  const statusApi = useApi(getAgentStatus, []);
  const invApi = useApi(getAgentInvestigations, []);
  const recApi = useApi(() => getRecoveryActions({ status: 'pending' }), []);

  const status = statusApi.data || {};
  const investigations = invApi.data?.items || invApi.data?.investigations || (Array.isArray(invApi.data) ? invApi.data : []);
  const recommendations = recApi.data?.items || recApi.data?.actions || (Array.isArray(recApi.data) ? recApi.data : []);

  const [pendingAction, setPendingAction] = useState(null);
  const [executing, setExecuting] = useState(false);

  const engaged = !statusApi.unavailable && !statusApi.networkError && !!statusApi.data;

  const confirmExecute = async () => {
    if (!pendingAction) return;
    setExecuting(true);
    const id = pendingAction.id;
    const res = await executeRecoveryAction(id, pendingAction.primary_action || 'retry');
    setExecuting(false);
    setPendingAction(null);
    if (res.ok) {
      toast('Recovery action executed', 'success', { description: `${id} — the backend is processing it.` });
      recApi.refresh();
      statusApi.refresh();
    } else if (res.status === 404) {
      toast('Recovery endpoint pending', 'error', {
        description: `POST /api/recovery/actions/${id}/execute is not implemented yet. Wire it to approve and run this action.`,
      });
    } else {
      toast('Action failed', 'error', { description: res.error });
    }
  };

  const reviewAction = (id) => {
    navigate('/recovery');
    toast('Opening recovery workspace', 'info', { description: id });
  };

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

      <Panel
        title="Recommended actions"
        subtitle={`AI-ranked actions with risk, impact and evidence · ${dateRange.label}`}
        actions={
          <Button variant="outline" size="sm" onClick={recApi.refresh}>
            <RefreshCw size={13} /> Refresh
          </Button>
        }
      >
        {recApi.loading ? (
          <WaitingState title="Loading recommendations…" />
        ) : recApi.networkError ? (
          <ErrorState error={recApi.error} onRetry={recApi.refresh} />
        ) : recApi.unavailable ? (
          <WaitingState
            title="Waiting for recovery recommendations"
            description="Recommended actions — retry eligible payments, avoid repeated retries, notify customers, escalate provider issues, refund where appropriate — appear here from /api/recovery/actions."
          />
        ) : recommendations.length === 0 ? (
          <RecommendationFallback />
        ) : (
          <div className="recos-grid">
            {recommendations.map((r) => (
              <AiRecommendationCard
                key={r.id}
                id={r.id}
                recommendation={r.recommended_action || r.action}
                reason={r.reason}
                confidence={r.recovery_probability ?? r.confidence}
                impact={r.expected_impact ?? r.impact}
                risk={r.risk}
                evidence={r.recommendation_reason || r.evidence}
                onExecute={(id) => setPendingAction(recommendations.find((x) => x.id === id) || { id })}
                onReview={reviewAction}
              />
            ))}
          </div>
        )}
      </Panel>

      <AgentChat dateRange={dateRange} />

      <ConfirmDialog
        open={!!pendingAction}
        onClose={() => setPendingAction(null)}
        onConfirm={confirmExecute}
        title="Execute recovery action?"
        description={
          pendingAction
            ? `${pendingAction.recommended_action || 'Retry eligible payments'} for ${pendingAction.id}. This will be routed through the backend with your current approval guardrails (${settings.requireApproval ? 'approval required' : 'auto-approve'}).`
            : undefined
        }
        confirmLabel="Execute"
        loading={executing}
      />
    </div>
  );
}