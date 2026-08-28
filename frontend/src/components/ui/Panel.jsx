export function Panel({ title, subtitle, actions, children, className = '', pad = true }) {
  return (
    <div className={`panel ${pad ? 'pad' : ''} ${className}`}>
      {(title || actions) && (
        <div className="panel-head">
          <div className="panel-title">
            {title ? <h2>{title}</h2> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions ? <div className="panel-actions">{actions}</div> : null}
        </div>
      )}
      {children}
    </div>
  );
}