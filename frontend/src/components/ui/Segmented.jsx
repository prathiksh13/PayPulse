export function Segmented({ options, value, onChange, size = 'md' }) {
  return (
    <div className={`segmented segmented-${size}`} role="tablist">
      {options.map((opt) => {
        const key = typeof opt === 'string' ? opt : opt.value;
        const label = typeof opt === 'string' ? opt : opt.label;
        const active = value === key;
        return (
          <button
            key={key}
            role="tab"
            aria-selected={active}
            className={`segment ${active ? 'active' : ''}`}
            onClick={() => onChange(key)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}