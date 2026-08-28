export function Badge({ tone = 'muted', children, className = '' }) {
  return <span className={`badge badge-${tone} ${className}`}>{children}</span>;
}