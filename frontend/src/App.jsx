import { useState } from 'react';
import { useApp, AppProvider } from './context/AppContext';
import { ToastProvider } from './context/ToastContext';
import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { Overview } from './pages/Overview';
import { Payments } from './pages/Payments';
import { UpiMandates } from './pages/UpiMandates';
import { CheckoutIntelligence } from './pages/CheckoutIntelligence';
import { AiAgent } from './pages/AiAgent';
import { Anomalies } from './pages/Anomalies';
import { RecoveryActions } from './pages/RecoveryActions';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { matchRoute } from './nav';
import { EmptyState } from './components/ui/EmptyState';
import { LayoutDashboard, Home } from 'lucide-react';
import { navigate } from './hooks/useHashRoute';

const PAGES = {
  overview: Overview,
  payments: Payments,
  'upi-mandates': UpiMandates,
  checkout: CheckoutIntelligence,
  'ai-agent': AiAgent,
  anomalies: Anomalies,
  recovery: RecoveryActions,
  reports: Reports,
  settings: Settings,
};

function NotFound() {
  return (
    <div className="page">
      <div className="panel pad">
        <EmptyState
          icon={LayoutDashboard}
          title="Page not found"
          description="The address you opened is not a valid PulseOps page."
          action={
            <button className="btn btn-primary" onClick={() => navigate('/')}>
              <Home size={14} /> Back to Overview
            </button>
          }
        />
      </div>
    </div>
  );
}

function Shell() {
  const { route } = useApp();
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeItem = matchRoute(route.path);
  const activeKey = activeItem.key;
  const Page = PAGES[activeKey] || NotFound;

  return (
    <div className="app-shell">
      <Sidebar activeKey={activeKey} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      <main className="main">
        <Topbar activeKey={activeKey} onOpenMobile={() => setMobileOpen(true)} />
        <Page key={activeKey} />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppProvider>
        <Shell />
      </AppProvider>
    </ToastProvider>
  );
}