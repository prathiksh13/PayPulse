import {
  LayoutDashboard, CreditCard, WalletCards, Activity, Bot,
  AlertTriangle, RefreshCw, FileText, Settings,
} from 'lucide-react';

export const NAV_ITEMS = [
  { key: 'overview', label: 'Overview', path: '/', icon: LayoutDashboard },
  { key: 'payments', label: 'Payments', path: '/payments', icon: CreditCard },
  { key: 'upi-mandates', label: 'UPI Mandates', path: '/upi-mandates', icon: WalletCards },
  { key: 'checkout', label: 'Checkout Intelligence', path: '/checkout', icon: Activity },
  { key: 'ai-agent', label: 'AI Operations Agent', path: '/ai-agent', icon: Bot },
  { key: 'anomalies', label: 'Anomalies', path: '/anomalies', icon: AlertTriangle },
  { key: 'recovery', label: 'Recovery Actions', path: '/recovery', icon: RefreshCw },
  { key: 'reports', label: 'Reports', path: '/reports', icon: FileText },
  { key: 'settings', label: 'Settings', path: '/settings', icon: Settings },
];

export const ROUTE_META = {
  overview: {
    title: 'Overview',
    eyebrow: 'Merchant operations / Overview',
    subtitle: 'A live view of payment health, risk, and recovery opportunities.',
  },
  payments: {
    title: 'Payments',
    eyebrow: 'Merchant operations / Payments',
    subtitle: 'Monitor every transaction, filter by status and investigate failures.',
  },
  'upi-mandates': {
    title: 'UPI Mandates',
    eyebrow: 'Merchant operations / UPI Mandates',
    subtitle: 'Recurring revenue health — mandate lifecycle, debits and failures.',
  },
  checkout: {
    title: 'Checkout Intelligence',
    eyebrow: 'Merchant operations / Checkout Intelligence',
    subtitle: 'Understand where customers drop off and why.',
  },
  'ai-agent': {
    title: 'AI Operations Agent',
    eyebrow: 'Merchant operations / AI Operations Agent',
    subtitle: 'Command center for detection, investigation and automated recovery.',
  },
  anomalies: {
    title: 'Anomalies',
    eyebrow: 'Merchant operations / Anomalies',
    subtitle: 'Every failure spike, conversion drop and unusual pattern, graded by severity.',
  },
  recovery: {
    title: 'Recovery Actions',
    eyebrow: 'Merchant operations / Recovery Actions',
    subtitle: 'Ranked opportunities to recover failed revenue, with approval control.',
  },
  reports: {
    title: 'Reports',
    eyebrow: 'Merchant operations / Reports',
    subtitle: 'Daily, failure, recovery, UPI, checkout and AI operations reports.',
  },
  settings: {
    title: 'Settings',
    eyebrow: 'Merchant operations / Settings',
    subtitle: 'Workspace, Razorpay connection, AI agent and notification preferences.',
  },
};

export function matchRoute(path) {
  for (const item of NAV_ITEMS) {
    if (item.path === path) return item;
  }
  return null;
}
