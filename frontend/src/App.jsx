import { useEffect, useState } from 'react';
import { useApp, AppProvider } from './context/AppContext';
import { ToastProvider } from './context/ToastContext';
import { AuthProvider, useAuth } from './context/AuthContext';
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
import { Login } from './pages/Login';
import { matchRoute } from './nav';
import { EmptyState } from './components/ui/EmptyState';
import { LayoutDashboard, Home, Sparkles } from 'lucide-react';
import { navigate } from './hooks/useHashRoute';
import { Landing } from './pages/Landing';

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
          description="The address you opened is not a valid PayPulse page."
          action={
            <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
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
  const activeKey = activeItem?.key;
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

function AppContent() {
  const { route } = useApp();
  const { isAuthenticated, booted } = useAuth();
  const path = route.path;

  // Route-based auth guard. The landing page is always public; app routes are
  // protected; an already-authenticated user on /login is sent to the dashboard.
  // Redirects happen here (via effect) so rendering never produces a wrong page.
  useEffect(() => {
    if (!booted) return;
    const inApp = path !== '/' && path !== '/landing' && path !== '/login';
    if (path === '/login' && isAuthenticated) {
      navigate('/dashboard');
    } else if (inApp && !isAuthenticated) {
      navigate('/login');
    }
  }, [path, isAuthenticated, booted]);

  if (!booted) {
    return (
      <div className="app-boot">
        <div className="login-brand">
          <span className="landing-mark"><Sparkles size={18} /></span>
          <strong>PayPulse</strong>
        </div>
        <div className="app-boot-spinner" />
      </div>
    );
  }

  // Landing is publicly accessible (never auto-redirects to login).
  if (path === '/' || path === '/landing') {
    return <Landing />;
  }

  // Login page. If already authenticated, the effect redirects to /dashboard.
  if (path === '/login') {
    return isAuthenticated ? null : <Login />;
  }

  // Protected app routes (dashboard, payments, …). Unauthenticated users are
  // redirected to /login by the effect — render nothing to avoid a flash.
  if (!isAuthenticated) {
    return null;
  }

  return <Shell />;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </AuthProvider>
    </ToastProvider>
  );
}
