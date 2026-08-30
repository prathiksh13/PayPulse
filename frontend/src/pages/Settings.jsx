import { useMemo, useState } from 'react';
import {
  Building2, Zap, Bell, ShieldCheck, Save, RefreshCw, Plug, Ban,
} from 'lucide-react';
import { getSettings, updateSettings } from '../api';
import { useApp } from '../context/AppContext';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { Panel } from '../components/ui/Panel';
import { Button } from '../components/ui/Button';
import { Field, TextInput, Select, Toggle } from '../components/ui/Field';
import { StatusBadge } from '../components/ui/StatusBadge';
import { ErrorState } from '../components/ui/ErrorState';

function ToggleRow({ title, description, checked, onChange, disabled }) {
  return (
    <div className="settings-row">
      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
      <Toggle checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}

const CONN_META = {
  connected: { label: 'Connected', tone: 'success' },
  disconnected: { label: 'Disconnected', tone: 'danger' },
  pending: { label: 'Pending', tone: 'warning' },
  test: { label: 'Test', tone: 'info' },
  live: { label: 'Live', tone: 'success' },
};

export function Settings() {
  const { settings, patchSettings, merchant, updateMerchant } = useApp();
  const toast = useToast();
  const api = useApi(getSettings, []);
  const [saving, setSaving] = useState(false);

  const backend = api.data || {};
  const conn = useMemo(
    () => ({
      razorpay: backend.razorpay?.connection_status || backend.razorpay?.status || (api.data ? backend.razorpay?.connection_status : null),
      apiStatus: backend.webhook?.api_status || backend.razorpay?.api_status || null,
      webhookStatus: backend.webhook?.status || backend.webhook?.webhook_status || null,
      environment: backend.razorpay?.environment || backend.environment || null,
    }),
    [backend, api.data],
  );

  const connKnown = !!api.data && !api.unavailable;

  const save = async () => {
    setSaving(true);
    const res = await updateSettings({ merchant, ai_agent: settings, });
    setSaving(false);
    if (res.ok) {
      toast('Settings saved', 'success', { description: 'Your preferences were synced to the backend.' });
    } else if (res.status === 404) {
      toast('Settings saved locally', 'warning', {
        description: 'PUT /api/settings is not implemented yet. Changes persist in this browser until the backend sync endpoint is live.',
        duration: 5200,
      });
    } else {
      toast('Could not save settings', 'error', { description: res.error });
    }
  };

  const sectionHead = (Icon, title, subtitle) => (
    <div className="section-head">
      <span className="icon-box"><Icon size={16} /></span>
      <div><strong>{title}</strong><span>{subtitle}</span></div>
    </div>
  );

  const hidden = api.networkError;

  return (
    <div className="page settings-page">
      {hidden ? (
        <ErrorState
          error={api.error}
          onRetry={api.refresh}
        />
      ) : null}

      {!hidden && api.unavailable ? (
        <div className="api-banner">
          <div>
            <strong>Settings API not connected</strong>
            <span>GET /api/settings and PUT /api/settings are not implemented yet. Changes are stored locally in this browser and will sync to the backend when the API goes live. No secret keys are ever displayed or stored here.</span>
          </div>
        </div>
      ) : null}

      {!hidden && api.data && (
        <div className="api-banner success-tint">
          <div>
            <strong>Backend settings connected</strong>
            <span>Razorpay connection and webhook status are reported by the backend. Key material stays server-side.</span>
          </div>
          <Button variant="outline" size="sm" onClick={api.refresh}><RefreshCw size={13} /> Resync</Button>
        </div>
      )}

      <div className="settings-grid">
        <Panel title="Merchant" subtitle="Workspace identity and environment">
          {sectionHead(Building2, 'Profile', 'How this workspace is identified across PayPulse, Razorpay and reports.')}
          <div className="settings-form">
            <Field label="Merchant name">
              <TextInput value={merchant.name} onChange={(e) => updateMerchant({ name: e.target.value })} placeholder="Merchant name" />
            </Field>
            <Field label="Workspace">
              <TextInput value={merchant.workspace} onChange={(e) => updateMerchant({ workspace: e.target.value })} placeholder="Workspace" />
            </Field>
            <Field label="Environment" hint="Live environment requires Razorpay production credentials on the backend.">
              <Select value={merchant.environment} onChange={(e) => updateMerchant({ environment: e.target.value })}>
                <option value="Test">Test</option>
                <option value="Live">Live</option>
              </Select>
            </Field>
          </div>
        </Panel>

        <Panel title="Razorpay" subtitle="Gateway connection health">
          {sectionHead(Plug, 'Connection', 'Status reported by the backend — credentials never leave the server.')}
          <div className="settings-form">
            <div className="settings-row">
              <div><strong>Connection status</strong><span>{connKnown ? 'Reported live by backend' : 'Waiting for backend'}</span></div>
              <StatusBadge value={connKnown ? conn.razorpay : null} meta={CONN_META} />
            </div>
            <div className="settings-row">
              <div><strong>Test / Live environment</strong><span>{connKnown ? 'Set on the backend' : 'Not yet reported'}</span></div>
              <StatusBadge value={connKnown ? conn.environment : null} meta={CONN_META} />
            </div>
            <div className="settings-row">
              <div><strong>API connection</strong><span>{connKnown ? 'Razorpay API reachable' : 'Not yet reported'}</span></div>
              <StatusBadge value={connKnown ? conn.apiStatus : null} meta={CONN_META} />
            </div>
            <div className="settings-row">
              <div><strong>Webhook status</strong><span>{connKnown ? 'Events flowing into the operations engine' : 'Not yet reported'}</span></div>
              <StatusBadge value={connKnown ? conn.webhookStatus : null} meta={CONN_META} />
            </div>
            <p className="field-hint">Razorpay key ID and secret are configured in backend/.env (RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET). They are not exposed in the browser.</p>
          </div>
        </Panel>

        <Panel title="AI Agent" subtitle="Detection and automation guardrails">
          {sectionHead(Zap, 'Agent behavior', 'Controls what the agent may do without human approval.')}
          <div className="settings-form">
            <ToggleRow title="Enable agent" description="Let PayPulse watch payment events and generate insights." checked={settings.aiEnabled} onChange={(v) => patchSettings({ aiEnabled: v })} />
            <ToggleRow title="Auto recovery" description="Execute low-risk recovery actions automatically." checked={settings.autoRecovery} onChange={(v) => patchSettings({ autoRecovery: v })} />
            <ToggleRow title="Require approval before actions" description="Every recovery action needs explicit consent." checked={settings.requireApproval} onChange={(v) => patchSettings({ requireApproval: v })} />
            <div className="field-pair">
              <Field label="Max retry attempts">
                <TextInput type="number" min={0} max={10} value={settings.maxRetryAttempts} onChange={(e) => patchSettings({ maxRetryAttempts: Number(e.target.value) })} />
              </Field>
              <Field label="Max recovery amount (₹)">
                <TextInput type="number" min={0} value={settings.maxRecoveryAmount} onChange={(e) => patchSettings({ maxRecoveryAmount: Number(e.target.value) })} />
              </Field>
            </div>
            <Field label="Risk threshold" hint="Actions above this risk level always require approval.">
              <Select value={settings.riskThreshold} onChange={(e) => patchSettings({ riskThreshold: e.target.value })}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </Select>
            </Field>
          </div>
        </Panel>

        <Panel title="Notifications" subtitle="Alert preferences">
          {sectionHead(Bell, 'Alerts', 'Where operational signals reach you.')}
          <div className="settings-form">
            <ToggleRow title="Email alerts" description="General operational alerts by email." checked={settings.notifyEmail} onChange={(v) => patchSettings({ notifyEmail: v })} />
            <ToggleRow title="Failure spike alerts" description="Notify when failures exceed the baseline." checked={settings.notifyFailureSpike} onChange={(v) => patchSettings({ notifyFailureSpike: v })} />
            <ToggleRow title="Recovery alerts" description="Updates on recovery batches in progress." checked={settings.notifyRecovery} onChange={(v) => patchSettings({ notifyRecovery: v })} />
            <ToggleRow title="Daily reports" description="Daily payment health digest." checked={settings.notifyDailyReport} onChange={(v) => patchSettings({ notifyDailyReport: v })} />
          </div>
        </Panel>

        <Panel title="Security" subtitle="Integrity and audit">
          {sectionHead(ShieldCheck, 'Security posture', 'Status of security controls — reported by backend when available.')}
          <div className="settings-form">
            <div className="settings-row">
              <div><strong>Webhook status</strong><span>{connKnown ? 'Backend-verified' : 'Not yet reported'}</span></div>
              <StatusBadge value={connKnown ? conn.webhookStatus : null} meta={CONN_META} />
            </div>
            <div className="settings-row">
              <div><strong>API status</strong><span>{connKnown ? 'Backend-reachable' : 'Not yet reported'}</span></div>
              <StatusBadge value={connKnown ? conn.apiStatus : null} meta={CONN_META} />
            </div>
            <ToggleRow title="Audit logging" description="Log every agent action to the audit trail." checked={settings.auditLogging} onChange={(v) => patchSettings({ auditLogging: v })} />
            <p className="field-hint"><Ban size={12} /> Secret keys, webhook secrets and API credentials are never rendered in the frontend.</p>
          </div>
        </Panel>
      </div>

      <div className="settings-save">
        <Button onClick={save} loading={saving} icon={Save}>
          Save changes
        </Button>
        <span className="muted">Stored locally until PUT /api/settings is live.</span>
      </div>
    </div>
  );
}
