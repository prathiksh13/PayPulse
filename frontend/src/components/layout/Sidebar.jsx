import { Bot, ChevronDown, Sparkles, Store, X } from 'lucide-react';
import { navigate } from '../../hooks/useHashRoute';
import { NAV_ITEMS } from '../../nav';
import { useApp } from '../../context/AppContext';
import { Dropdown } from '../ui/Dropdown';
import { useApi } from '../../hooks/useApi';
import { getAgentStatus } from '../../api';

function MerchantSwitcher() {
  const { merchant } = useApp();
  return (
    <Dropdown
      width={250}
      trigger={() => (
        <button className="merchant">
          <div className="merchant-avatar">
            <Store size={15} />
          </div>
          <div className="merchant-copy">
            <strong>{merchant.name}</strong>
            <span>
              {merchant.workspace} · {merchant.environment} env
            </span>
          </div>
          <ChevronDown size={15} />
        </button>
      )}
    >
      {({ close }) => (
        <>
          <div className="menu-label">Workspace</div>
          <div className="dropdown-item active">
            <Store size={15} />
            <span>{merchant.name} · {merchant.environment}</span>
          </div>
          <div className="menu-divider" />
          <div className="menu-hint">Workspaces are synced from the backend once the merchant API is available.</div>
        </>
      )}
    </Dropdown>
  );
}

export function Sidebar({ activeKey, mobileOpen, onCloseMobile }) {
  const agent = useApi(getAgentStatus, []);

  const agentState = agent.networkError
    ? { tone: 'off', text: 'Backend offline' }
    : agent.unavailable
      ? { tone: 'off', text: 'Agent endpoints pending' }
      : agent.loading
        ? { tone: '', text: 'Checking…' }
        : { tone: '', text: 'Online · watching payments' };

  return (
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand">
        <div className="brand-mark">
          <Sparkles size={17} />
        </div>
        <div>
          <strong>PayPulse</strong>
          <span>Payment Intelligence</span>
        </div>
        <button className="mobile-close" onClick={onCloseMobile} aria-label="Close menu">
          <X size={18} />
        </button>
      </div>

      <MerchantSwitcher />

      <nav>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              className={`nav-item ${activeKey === item.key ? 'active' : ''}`}
              onClick={() => {
                navigate(item.path);
                onCloseMobile();
              }}
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="agent-mini">
          <div className="agent-orb">
            <Bot size={16} />
          </div>
          <div>
            <strong>AI Agent</strong>
            <span>{agentState.text}</span>
          </div>
          <span className={`online-dot ${agentState.tone === 'off' ? 'off' : ''}`} />
        </div>
      </div>
    </aside>
  );
}
