const inr0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int0 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

export const fmtINR = (n) => (n == null || Number.isNaN(n) ? '—' : inr0.format(n));
export const fmtINRExact = (n) => (n == null || Number.isNaN(n) ? '—' : inr2.format(n));
export const fmtNum = (n) => (n == null || Number.isNaN(n) ? '—' : int0.format(n));
export const fmtCompact = (n) => {
  if (n == null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(2).replace(/\.00$/, '')}Cr`;
  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(2).replace(/\.00$/, '')}L`;
  if (abs >= 1e3) return `₹${(n / 1e3).toFixed(1).replace(/\.0$/, '')}K`;
  return fmtINR(n);
};
export const fmtPct = (n) => (n == null || Number.isNaN(n) ? '—' : `${Math.round(n * 10) / 10}%`);

export function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function timeAgo(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return 'just now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(iso);
}

export function titleCase(s) {
  if (!s) return '—';
  return String(s)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function toISODate(d) {
  const date = d instanceof Date ? d : new Date(d);
  if (Number.isNaN(date.getTime())) return '';
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export const PRESET_RANGES = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'last_7', label: 'Last 7 days' },
  { key: 'last_30', label: 'Last 30 days' },
  { key: 'custom', label: 'Custom range' },
];

export function presetRange(preset, custom = null) {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const today = toISODate(start);
  const yesterday = toISODate(new Date(start.getTime() - 86400000));
  const minusDays = (n) => toISODate(new Date(start.getTime() - (n - 1) * 86400000));
  switch (preset) {
    case 'today': return { preset, label: 'Today', from: today, to: today };
    case 'yesterday': return { preset, label: 'Yesterday', from: yesterday, to: yesterday };
    case 'last_7': return { preset, label: 'Last 7 days', from: minusDays(7), to: today };
    case 'last_30': return { preset, label: 'Last 30 days', from: minusDays(30), to: today };
    case 'custom':
      return custom && custom.from && custom.to
        ? { preset, label: 'Custom range', from: custom.from, to: custom.to }
        : { preset, label: 'Custom range', from: minusDays(7), to: today };
    default: return { preset: 'last_7', label: 'Last 7 days', from: minusDays(7), to: today };
  }
}

export function asArray(v) {
  if (v === undefined || v === null) return [];
  return Array.isArray(v) ? v : [v];
}
