export function StatCard({ label, value, sub, icon: Icon, tone = 'muted', loading = false }) {
  const longValue = typeof value === 'string' && value.length > 11;
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        {Icon && (
          <span className="icon-box">
            <Icon size={16} />
          </span>
        )}
      </div>
      <div className={`stat-value ${longValue ? 'long' : ''}`}>
        {loading ? <span className="skeleton" style={{ display: 'inline-block', width: '60%', height: 20, borderRadius: 6 }} /> : value}
      </div>
      <div className="stat-bottom">
        {loading ? <span className="skeleton skeleton-70" /> : <span className="muted">{sub}</span>}
      </div>
    </div>
  );
}