import { Search } from 'lucide-react';

export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`field ${className}`}>
      {label ? <span className="field-label">{label}</span> : null}
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function TextInput({ icon: Icon, className = '', ...rest }) {
  return (
    <div className={`input-wrap ${Icon || rest?.type === 'search' ? 'with-icon' : ''}`}>
      {Icon ? <Icon size={15} className="input-icon" /> : rest?.type === 'search' ? <Search size={15} className="input-icon" /> : null}
      <input className={`input ${className}`} {...rest} />
    </div>
  );
}

export function Select({ className = '', children, ...rest }) {
  return (
    <select className={`input select ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Toggle({ checked, onChange, disabled = false, label, description }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      className={`toggle ${checked ? 'on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="toggle-label" aria-hidden="true" />
      <span className="toggle-knob" />
    </button>
  );
}